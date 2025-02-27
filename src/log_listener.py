from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
import json


cassandra_host = "provide host name"
cassandra_user = "provide user"
cassandra_pwd  = "provide password"
cassandra_port = 9042
key_space      = "provide keyspace"
table_name     = "provide table"
kafka_server   = "kafka:9092"
kafka_topic    = "provide kafka topic"

#Spark Session creation configured to interact with MongoDB
spark = SparkSession.builder.appName("pyspark-notebook").\
config("spark.jars.packages","org.apache.spark:spark-sql-kafka-0-10_2.12:3.0.0,com.datastax.spark:spark-cassandra-connector_2.12:3.0.0,com.datastax.spark:spark-cassandra-connector-driver_2.12:3.0.0").\
config("spark.cassandra.connection.host",cassandra_host).\
config("spark.cassandra.auth.username",cassandra_user).\
config("spark.cassandra.auth.password",cassandra_pwd).\
getOrCreate()



#Read data from Kafka topic
split_logic = split(col("url"),"\.").getItem(1)
log_data = spark\
  .readStream\
  .format("kafka")\
  .option("kafka.bootstrap.servers",kafka_server)\
  .option("subscribe", kafka_topic)\
  .option("startingOffsets", "earliest")\
  .load()\
  .selectExpr("split(value,',')[1] as host",
              "split(value,',')[2] as time",
              "split(value,',')[3] as method",
              "split(value,',')[4] as url",
              "split(value,',')[5] as response",
              "split(value,',')[6] as bytes"
             )\
  .withColumn("time_added",unix_timestamp())\
  .withColumn("extension",when(split_logic.isNull(),"None").otherwise(split_logic))




def process_row(df, epoch_id):
    """Writes data to Cassandra and HDFS location

    Parameters
    ----------
    df : DataFrame
        Streaming Dataframe
    epoch_id : int
        Unique id for each micro batch/epoch
    """
    df.write\
    .format("org.apache.spark.sql.cassandra")\
    .mode('append')\
    .options(table="nasalog", keyspace="loganalysis")\
    .save() #hot path
    df.write.csv("hdfs://namenode:8020/output/logs/",mode="append") #cold path




log_data \
    .writeStream \
    .option("checkpointLocation", "checkpoint/data") \
    .foreachBatch(process_row) \
    .start() \
    .awaitTermination()