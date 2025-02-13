import os
import argparse
from pathlib import Path

from pyspark.sql import functions as F

from plantclef.spark import get_spark


spark = get_spark()


def get_home_dir():
    """Get the home directory for the current user on PACE."""
    return Path(os.path.expanduser("~"))


def get_subset_dataframe(
    spark,
    train_data_path: str,
    top_n: int = 20,
):
    """
    Reads a parquet dataset from train_path, computes the top N species by image count,
    and returns a DataFrame filtered to only include images belonging to these species.

    Parameters:
        spark (SparkSession): The active Spark session.
        train_data_path (str): The path to the train parquet files.
        top_n (int): The number of top species to select (default: 20).

    Returns:
        DataFrame: A subset of the original DataFrame with images for the top N species.
    """
    # read the parquet files into a spark DataFrame
    train_df = spark.read.parquet(train_data_path)

    # get top species by number of images
    grouped_train_df = (
        train_df.groupBy(["species", "species_id"])
        .agg(F.count("species_id").alias("n"))
        .orderBy(F.col("n").desc())
    ).cache()  # cache this because it's used twice

    # get subset of top N species
    top_n_species = grouped_train_df.limit(top_n).select("species_id").cache()
    subset_df = train_df.join(F.broadcast(top_n_species), on="species_id", how="inner")

    return subset_df


def parse_args():
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description="Process images and metadata for a dataset stored on PACE."
    )
    parser.add_argument(
        "--cores",
        type=int,
        default=os.cpu_count(),
        help="Number of cores used in Spark driver",
    )
    parser.add_argument(
        "--memory",
        type=str,
        default="16g",
        help="Amount of memory to use in Spark driver",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top species to include (default: 20)",
    )

    return parser.parse_args()


def main():
    """
    Main function that processes data and writes the
    output dataframe to plantclef directory on PACE.
    """
    args = parse_args()

    # initialize Spark with settings for the driver
    spark = get_spark(
        cores=args.cores, memory=args.memory, **{"spark.sql.shuffle.partitions": 500}
    )

    # set input and output paths
    home_dir = get_home_dir()
    data_path = f"{home_dir}/p-dsgt_clef2025-0/shared/plantclef/data/parquet_files/"
    input_path = f"{data_path}/train"
    output_path = f"{data_path}/subset_top{args.top_n}_train"

    # get subset dataframe with top N species
    subset_df = get_subset_dataframe(
        spark=spark,
        train_data_path=input_path,
        top_n=args.top_n,
    )

    # write the DataFrame to PACE in Parquet format
    subset_df.write.mode("overwrite").parquet(output_path)
    print(f"Subset dataframe written to: {output_path}")


if __name__ == "__main__":
    main()
