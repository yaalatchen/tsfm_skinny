# Copyright contributors to the TSFM project
#
"""Basic functions and utilities"""

# Standard
from datetime import datetime
from distutils.util import strtobool
from typing import List, Optional, Union

# Third Party
import pandas as pd


def select_by_timestamp(
    df: pd.DataFrame,
    timestamp_column: str = "timestamp",
    start_timestamp: Optional[Union[str, datetime]] = None,
    end_timestamp: Optional[Union[str, datetime]] = None,
):
    if not start_timestamp and not end_timestamp:
        raise ValueError(
            "At least one of start_timestamp or end_timestamp must be specified."
        )
    elif not start_timestamp:
        return df[df[timestamp_column] < end_timestamp]
    elif not end_timestamp:
        return df[df[timestamp_column] >= start_timestamp]
    else:
        return df[
            (df[timestamp_column] >= start_timestamp)
            & (df[timestamp_column] < end_timestamp)
        ]


def select_by_index(
    df: pd.DataFrame,
    id_columns: Optional[List[str]] = None,
    start_index: Optional[int] = None,
    end_index: Optional[int] = None,
):
    if not start_index and not end_index:
        raise ValueError("At least one of start_index or stop_index must be specified.")

    def _split_group_by_index(
        group_df: pd.DataFrame,
        start_index: Optional[int] = None,
        end_index: Optional[int] = None,
    ):
        if not start_index:
            return group_df.iloc[:end_index,]
        elif not end_index:
            return group_df.iloc[start_index:,]
        else:
            return group_df.iloc[start_index:end_index, :]

    if not id_columns:
        return _split_group_by_index(
            df, start_index=start_index, end_index=end_index
        ).copy()

    groups = df.groupby(id_columns)
    result = []
    for name, group in groups:
        result.append(
            _split_group_by_index(group, start_index=start_index, end_index=end_index)
        )

    return pd.concat(result)


def convert_tsf_to_dataframe(
    full_file_path_and_name,
    replace_missing_vals_with="NaN",
    value_column_name="series_value",
):
    col_names = []
    col_types = []
    all_data = {}
    line_count = 0
    frequency = None
    forecast_horizon = None
    contain_missing_values = None
    contain_equal_length = None
    found_data_tag = False
    found_data_section = False
    started_reading_data_section = False

    with open(full_file_path_and_name, "r", encoding="cp1252") as file:
        for line in file:
            # Strip white space from start/end of line
            line = line.strip()

            if line:
                if line.startswith("@"):  # Read meta-data
                    if not line.startswith("@data"):
                        line_content = line.split(" ")
                        if line.startswith("@attribute"):
                            if (
                                len(line_content) != 3
                            ):  # Attributes have both name and type
                                raise Exception("Invalid meta-data specification.")

                            col_names.append(line_content[1])
                            col_types.append(line_content[2])
                        else:
                            if (
                                len(line_content) != 2
                            ):  # Other meta-data have only values
                                raise Exception("Invalid meta-data specification.")

                            if line.startswith("@frequency"):
                                frequency = line_content[1]
                            elif line.startswith("@horizon"):
                                forecast_horizon = int(line_content[1])
                            elif line.startswith("@missing"):
                                contain_missing_values = bool(
                                    strtobool(line_content[1])
                                )
                            elif line.startswith("@equallength"):
                                contain_equal_length = bool(strtobool(line_content[1]))

                    else:
                        if len(col_names) == 0:
                            raise Exception(
                                "Missing attribute section. Attribute section must come before data."
                            )

                        found_data_tag = True
                elif not line.startswith("#"):
                    if len(col_names) == 0:
                        raise Exception(
                            "Missing attribute section. Attribute section must come before data."
                        )
                    elif not found_data_tag:
                        raise Exception("Missing @data tag.")
                    else:
                        if not started_reading_data_section:
                            started_reading_data_section = True
                            found_data_section = True
                            all_series = []

                            for col in col_names:
                                all_data[col] = []

                        full_info = line.split(":")

                        if len(full_info) != (len(col_names) + 1):
                            raise Exception("Missing attributes/values in series.")

                        series = full_info[len(full_info) - 1]
                        series = series.split(",")

                        if len(series) == 0:
                            raise Exception(
                                "A given series should contains a set of comma separated numeric values. At least one numeric value should be there in a series. Missing values should be indicated with ? symbol"
                            )

                        numeric_series = []

                        for val in series:
                            if val == "?":
                                numeric_series.append(replace_missing_vals_with)
                            else:
                                numeric_series.append(float(val))

                        if numeric_series.count(replace_missing_vals_with) == len(
                            numeric_series
                        ):
                            raise Exception(
                                "All series values are missing. A given series should contains a set of comma separated numeric values. At least one numeric value should be there in a series."
                            )

                        all_series.append(pd.Series(numeric_series).array)

                        for i in range(len(col_names)):
                            att_val = None
                            if col_types[i] == "numeric":
                                att_val = int(full_info[i])
                            elif col_types[i] == "string":
                                att_val = str(full_info[i])
                            elif col_types[i] == "date":
                                att_val = datetime.strptime(
                                    full_info[i], "%Y-%m-%d %H-%M-%S"
                                )
                            else:
                                raise Exception(
                                    "Invalid attribute type."
                                )  # Currently, the code supports only numeric, string and date types. Extend this as required.

                            if att_val is None:
                                raise Exception("Invalid attribute value.")
                            else:
                                all_data[col_names[i]].append(att_val)

                line_count = line_count + 1

        if line_count == 0:
            raise Exception("Empty file.")
        if len(col_names) == 0:
            raise Exception("Missing attribute section.")
        if not found_data_section:
            raise Exception("Missing series information under data section.")

        all_data[value_column_name] = all_series
        loaded_data = pd.DataFrame(all_data)

        return (
            loaded_data,
            frequency,
            forecast_horizon,
            contain_missing_values,
            contain_equal_length,
        )
