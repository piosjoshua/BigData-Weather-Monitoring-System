
"""
Real-Time Earthquake Monitoring System

Pipeline:
USGS API -> Kafka -> Apache Spark -> MongoDB Atlas
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    from_json,
    count,
    avg,
    max as spark_max,
    min as spark_min
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    LongType,
    IntegerType
)

# ------------------------------------
# 1. ENVIRONMENT CONFIGURATION
# ------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

MONGODB_URI = os.getenv("MONGODB_URI")

DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "earthquake_db"
)

COLLECTION = os.getenv(
    "MONGODB_COLLECTION",
    "earthquake_events"
)

KAFKA_BROKER = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092"
)

KAFKA_TOPIC = os.getenv(
    "KAFKA_TOPIC",
    "earthquake_stream"
)

if not MONGODB_URI:
    raise RuntimeError(
        "MONGODB_URI is missing from .env"
    )

# Explicit LOCAL checkpoint directory
CHECKPOINT_DIR = (
    BASE_DIR / "checkpoints" / "earthquake_stream"
)

CHECKPOINT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CHECKPOINT_URI = CHECKPOINT_DIR.as_uri()


# ------------------------------------
# 2. MONGODB CONNECTION
# ------------------------------------

def initialize_mongodb():

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10000
    )

    try:
        client.admin.command("ping")

        collection = client[DATABASE][COLLECTION]

        collection.create_index(
            "event_id",
            unique=True
        )

        print("MongoDB Atlas connected successfully!")
        print(f"Database: {DATABASE}")
        print(f"Collection: {COLLECTION}")

    finally:
        client.close()


# ------------------------------------
# 3. APACHE SPARK SESSION
# ------------------------------------

spark = (
    SparkSession.builder
    .master("local[*]")
    .appName("EarthquakeStreamingPipeline")
    .config("spark.sql.shuffle.partitions", "4")
    .config("spark.hadoop.fs.defaultFS", "file:///")
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

print("Apache Spark initialized successfully!")


# ------------------------------------
# 4. EARTHQUAKE DATA SCHEMA
# ------------------------------------

earthquake_schema = StructType([
    StructField("event_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("updated_ms", LongType(), True),
    StructField("magnitude", DoubleType(), True),
    StructField("place", StringType(), True),
    StructField("latitude", DoubleType(), True),
    StructField("longitude", DoubleType(), True),
    StructField("depth_km", DoubleType(), True),
    StructField("tsunami", IntegerType(), True),
    StructField("source", StringType(), True),
    StructField("metric_type", StringType(), True),
    StructField("value", DoubleType(), True),
    StructField("sensor_id", StringType(), True),
    StructField("location", StringType(), True),
    StructField("unit", StringType(), True)
])


# ------------------------------------
# 5. READ DATA FROM KAFKA
# ------------------------------------

def read_kafka_stream():

    print("Connecting Spark to Kafka...")

    kafka_stream = (
        spark.readStream
        .format("kafka")
        .option(
            "kafka.bootstrap.servers",
            KAFKA_BROKER
        )
        .option(
            "subscribe",
            KAFKA_TOPIC
        )
        .option(
            "startingOffsets",
            "earliest"
        )
        .load()
    )

    print("Kafka streaming source configured!")

    return kafka_stream


# ------------------------------------
# 6. PROCESS EARTHQUAKE DATA
# ------------------------------------

def process_earthquakes(kafka_stream):

    print("Processing earthquake stream...")

    json_stream = kafka_stream.selectExpr(
        "CAST(value AS STRING) AS json_data"
    )

    earthquake_data = (
        json_stream
        .select(
            from_json(
                col("json_data"),
                earthquake_schema
            ).alias("data")
        )
        .select("data.*")
    )

    cleaned_data = (
        earthquake_data
        .filter(col("event_id").isNotNull())
        .filter(col("magnitude").isNotNull())
        .filter(col("latitude").between(-90, 90))
        .filter(col("longitude").between(-180, 180))
    )

    print("Earthquake processing configured!")

    return cleaned_data


# ------------------------------------
# 7. SAVE DATA TO MONGODB
# ------------------------------------

def save_to_mongodb(batch_df, batch_id):

    if batch_df.isEmpty():
        print(f"Batch {batch_id}: No new records.")
        return

    print(f"\nProcessing Spark batch: {batch_id}")

    # Spark data aggregation
    statistics = batch_df.agg(
        count("*").alias("total_records"),
        avg("magnitude").alias("average_magnitude"),
        spark_max("magnitude").alias("highest_magnitude"),
        spark_min("magnitude").alias("lowest_magnitude")
    )

    print("Earthquake batch statistics:")
    statistics.show(truncate=False)

    client = MongoClient(
        MONGODB_URI,
        serverSelectionTimeoutMS=10000
    )

    try:
        collection = client[DATABASE][COLLECTION]

        operations = []
        processed = 0

        for row in batch_df.toLocalIterator():

            earthquake = row.asDict(recursive=True)

            event_id = earthquake["event_id"]

            # Upsert by unique earthquake event ID
            operations.append(
                UpdateOne(
                    {"event_id": event_id},
                    {"$set": earthquake},
                    upsert=True
                )
            )

            if len(operations) >= 500:
                collection.bulk_write(
                    operations,
                    ordered=True
                )

                processed += len(operations)
                operations.clear()

        if operations:
            collection.bulk_write(
                operations,
                ordered=True
            )

            processed += len(operations)

        print(
            f"Batch {batch_id}: "
            f"Processed {processed} records."
        )

        print(
            "Total unique earthquake events in MongoDB:",
            collection.count_documents({})
        )

    finally:
        client.close()


# ------------------------------------
# 8. START SPARK STRUCTURED STREAMING
# ------------------------------------

def start_streaming():

    initialize_mongodb()

    kafka_stream = read_kafka_stream()

    earthquake_stream = process_earthquakes(
        kafka_stream
    )

    print("Starting real-time Spark streaming...")
    print(f"Checkpoint location: {CHECKPOINT_URI}")

    query = (
        earthquake_stream.writeStream
        .foreachBatch(save_to_mongodb)
        .outputMode("append")
        .option(
            "checkpointLocation",
            CHECKPOINT_URI
        )
        .trigger(
            processingTime="15 seconds"
        )
        .start()
    )

    print("Spark streaming started successfully!")
    print("Waiting for earthquake events...")

    query.awaitTermination()


# ------------------------------------
# 9. MAIN PROGRAM
# ------------------------------------

if __name__ == "__main__":

    try:
        start_streaming()

    except KeyboardInterrupt:
        print("Spark streaming stopped by user.")

    finally:
        spark.stop()
        print("Spark session closed.")



