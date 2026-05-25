import os
import sys
import psycopg2 
# Đồng bộ hóa môi trường Python của Spark Worker với Conda Driver
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable

from loguru import logger
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, udf, round
from pyspark.sql.types import StructType, StructField, StringType, DoubleType
from transform_utils import clean_area, clean_price

kafka_raw_schema = StructType([
    StructField("ID", StringType(), True),
    StructField("Title", StringType(), True),
    StructField("Price_Raw", StringType(), True),
    StructField("Area_Raw", StringType(), True),
    StructField("Location", StringType(), True),
    StructField("Published_Date", StringType(), True),
    StructField("URL", StringType(), True)
])

# Register UDFs
clean_area_udf = udf(clean_area, DoubleType())
clean_price_udf = udf(clean_price, DoubleType())

def init_postgres_table():
    conn = psycopg2.connect(
        host="localhost",
        port="5432",
        user="user",
        password="password",
        dbname="bds"
    )
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS price_logs (
        id VARCHAR(255) NOT NULL PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        total_price_vnd DOUBLE PRECISION,
        area_m2 DOUBLE PRECISION,
        unit_price_m2 DOUBLE PRECISION,
        location VARCHAR(255),
        published_date TIMESTAMP,
        url VARCHAR(255)
    );
    """)
    cur.execute("ALTER TABLE price_logs ADD COLUMN IF NOT EXISTS location VARCHAR(255);")
    conn.commit()
    conn.close()
    


def main():
    init_postgres_table()
    
    logger.info("\n[Spark Streaming] Đang khởi tạo SparkSession...")

    spark = SparkSession.builder \
        .appName("BDS-Market-Volatility-Processing") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.13:4.1.2") \
        .config("spark.sql.shuffle.partitions", "2") \
        .getOrCreate()

    # Phân phối file transform_utils.py tới các Spark Worker để tránh lỗi ModuleNotFoundError
    spark.sparkContext.addPyFile(os.path.join(os.path.dirname(__file__), "transform_utils.py"))

    spark.sparkContext.setLogLevel("ERROR")

    logger.info("[Spark Streaming] Đang kết nối và listen topic Kafka 'bds.raw'...")

    kafka_stream_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "localhost:9092") \
        .option("subscribe", "bds.raw") \
        .option("startingOffsets", "earliest") \
        .load()

    #Decode data json from kafka
    json_parsed_df = kafka_stream_df \
        .selectExpr("CAST(value AS STRING) as json_str") \
        .select(from_json(col("json_str"), kafka_raw_schema).alias("data")) \
        .select("data.*")


    #Execute cleaning & transforming pipeline
    df_with_area = json_parsed_df.withColumn("Area_M2", clean_area_udf(col("Area_Raw")))
    
    df_with_price = df_with_area.withColumn("Price_VND", clean_price_udf(col("Price_Raw"), col("Area_M2")))
    
    # Keep only rows with valid numeric inputs to avoid NULL numeric fields in DB.
    df_valid = df_with_price.filter(
        col("Area_M2").isNotNull()
        & col("Price_VND").isNotNull()
        & (col("Area_M2") > 0)
    )

    final_clean_df = df_valid.select(
        col("ID").alias("post_id"),
        col("Title").alias("title"),
        col("Price_VND").alias("total_price_vnd"),
        col("Area_M2").alias("area_m2"),
        # Tính thêm đơn giá chuẩn đơn vị VND/m2 làm chỉ số phân tích biến động
        round(col("Price_VND") / col("Area_M2"), 2).alias("unit_price_m2"),
        col("Location").alias("location"),
        col("Published_Date").alias("published_date"),
        col("URL").alias("url")
    )

    def write_to_db(batch_df, batch_id):
        logger.info(f"[Batch {batch_id}] Writing {batch_df.count()} records to PostgreSQL")
        
        conn = psycopg2.connect(
            host="localhost",
            port="5432",
            user="user",
            password="password",
            dbname="bds"
        )
        cur = conn.cursor()
        
        for row in batch_df.collect():
            try:
                cur.execute("""
                    INSERT INTO price_logs (
                        id, title, total_price_vnd, area_m2,
                        unit_price_m2, location, published_date, url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    row.post_id, 
                    row.title, 
                    row.total_price_vnd, 
                    row.area_m2, 
                    row.unit_price_m2, 
                    row.location, 
                    row.published_date, 
                    row.url
                ))
            except psycopg2.IntegrityError:
                # Tránh duplicate ID nếu chạy lại
                pass
            except Exception as e:
                logger.error(f"Error inserting row: {e}")
                
        conn.commit()
        conn.close()
        
        logger.info(f"[Batch {batch_id}] Write complete.")


if __name__ == "__main__":
    main()