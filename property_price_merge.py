"""Build the acquisition-price benchmarks used by the Group 6 analysis.

Workflow
--------
1. Read the already-cleaned, suburb-assigned Airbnb listings.
2. Match 2025 VGV sale-price medians by suburb and House/Unit class.
3. Match September 2025 moving-annual DFFH rents by market, class and bedrooms.
4. Scale each sale median using the bedroom-specific rent / typical rent ratio.
5. Export the listing-level CSV and supporting matching/coverage audit tables.

Method and limitations
----------------------
Purchase-price proxy = VGV suburb/class median * (bedroom rent / typical rent).
Typical rent is the letting-count-weighted median of bedroom-category median
weekly rents in the matched DFFH market and class. It is NOT the pooled median
of individual leases. The weighted mean is exported only as an audit alternative.
The calculation assumes relative rents approximate relative purchase prices
across bedroom categories. This is our assumption, not a government valuation
method. No log transformation or fitted price regression is used here.

VGV has no bedroom or bathroom fields. DFFH supplies 1/2/3-bedroom flat categories
and 2/3/4-bedroom house categories. At least two valid bedroom categories are
required for an adjustment. Suburbs are matched to explicitly named rental
markets, with a labelled council-level fallback where supported; this is not
an average of neighbouring suburbs. Unsupported or missing matches stay blank
and have an explanation in bedroom_adjustment_status.

House/Unit classes are broad approximations of Airbnb property types. Condition,
land area and bathrooms are not acquisition-price adjustments. These are
screening benchmarks, not observed listing purchase prices or formal valuations.
Listing-level gross yields use supplied Inside Airbnb estimated_revenue_l365d,
not the regression predictions later used in the comprehensive notebook.
Neither measure is net profit or true ROI. Purchase-price uncertainty is not
estimated by this script.

Separate nightly-price comparisons are retained for compatibility. They use
Airbnb prices and bedroom/bathroom groups, NEVER to calculate purchase prices.
Their minimum group size is a practical fallback threshold, not a significance
test. Original input fields and existing output column names are preserved.

Sources
-------
* Valuer-General Victoria. Houses by suburb 2015-2025; Units by suburb
  2015-2025 [data sets]. Use the 2025 median column only.
  https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics
* Department of Families, Fairness and Housing / Homes Victoria. Moving annual
  rent by suburb - September quarter 2025 [data set]. Use the Sep 2025 Count
  and Median columns, not a model fitted to the workbook's full time series.
  https://www.dffh.vic.gov.au/publications/rental-report
* Inside Airbnb. Melbourne listings [data set]. The cleaned input is produced
  upstream; last_scraped records the listing-level snapshot dates.
  https://insideairbnb.com/get-the-data/

The output retains source URLs, filenames, periods, VGV source markers and DFFH
matching methods. Three additional reference columns name the original sources.
Publication dates are not inferred from the year covered by a data set.

Running from the project root
-----------------------------
Requires Python 3.10+ with numpy, pandas and openpyxl. Prepare
listings_clean_merged_with_suburb.csv in the cleaning notebook first. Download
the three named source workbooks into Testing; this script does not download
data or change its source period automatically. For the full proxy run:

python property_price_merge.py listings_clean_merged_with_suburb.csv Testing/VGV_houses_by_suburb_2015-2025.xlsx Testing/VGV_units_by_suburb_2015-2025.xlsx . --dffh-workbook Testing/DFFH_moving_annual_rent_by_suburb_September_2025.xlsx --audit-directory Testing

The full CSV is written to the project root and audit files to Testing. Use a
different output directory for a trial run. Existing named output files in the
chosen directories are replaced. Omitting --dffh-workbook intentionally produces
only the unadjusted VGV benchmarks and nightly-price comparisons.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd


# 1. Source periods and the explicit rental-market name crosswalk.
VGV_SOURCE_URL = (
    "https://www.land.vic.gov.au/valuations/resources-and-reports/"
    "property-sales-statistics"
)
VGV_SOURCE_YEAR = 2025
DFFH_SOURCE_URL = "https://www.dffh.vic.gov.au/publications/rental-report"
DFFH_SOURCE_PERIOD = "Sep 2025"
LISTINGS_SOURCE_REFERENCE = (
    "Inside Airbnb, listings. https://insideairbnb.com/get-the-data/"
)
VGV_SOURCE_REFERENCES = {
    "House": "Valuer-General Victoria, Houses by suburb 2015-2025 (2025 median).",
    "Unit": "Valuer-General Victoria, Units by suburb 2015-2025 (2025 median).",
}
DFFH_SOURCE_REFERENCE = (
    "DFFH / Homes Victoria, Moving annual rent by suburb (Sep 2025)."
)
DFFH_WORKSHEETS = {
    "1 bedroom flat": ("Unit", 1),
    "2 bedroom flat": ("Unit", 2),
    "3 bedroom flat": ("Unit", 3),
    "2 bedroom house": ("House", 2),
    "3 bedroom house": ("House", 3),
    "4 bedroom house": ("House", 4),
}

# The DFFH workbook uses a handful of market labels whose word order differs
# from the official locality names assigned to the Airbnb coordinates. Only
# unambiguous aliases are included; nearby unnamed suburbs are not inferred.
DFFH_LOCALITY_ALIASES = {
    "CBD": "MELBOURNE",
    "ST KILDA RD": "MELBOURNE",
    "EAST BRUNSWICK": "BRUNSWICK EAST",
    "WEST BRUNSWICK": "BRUNSWICK WEST",
    "EAST HAWTHORN": "HAWTHORN EAST",
    "EAST ST KILDA": "ST KILDA EAST",
    "WEST ST KILDA": "ST KILDA WEST",
}


# 2. Read and standardise the published source tables.
def normalise_suburb(value: object) -> object:
    """Return a normalised string or pd.NA, leaving the displayed suburb intact."""
    if pd.isna(value):
        return pd.NA
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^A-Z0-9]+", " ", text.upper()).strip()
    return re.sub(r"\s+", " ", text) or pd.NA


def classify_dwelling(property_type: object) -> str:
    """Map only clearly comparable entire dwellings to the VGV house/unit classes."""
    text = str(property_type).strip().casefold()

    unit_types = {
        "entire rental unit",
        "entire condo",
        "entire serviced apartment",
        "entire loft",
    }
    house_types = {
        "entire home",
        "entire townhouse",
        "entire cottage",
        "entire villa",
        "entire bungalow",
        "entire vacation home",
    }

    if text in unit_types:
        return "Unit"
    if text in house_types:
        return "House"
    return "Unclassified"


def read_vgv_annual_medians(path: str | Path, dwelling_class: str) -> pd.DataFrame:
    """Read the 2025 median column from a VGV suburb workbook."""
    path = Path(path)
    raw = pd.read_excel(path, sheet_name=0, header=None)

    locality_rows = raw.index[
        raw.iloc[:, 0].astype("string").str.strip().str.casefold().eq("locality")
    ].tolist()
    if len(locality_rows) != 1:
        raise ValueError(f"Expected one Locality header row in {path.name}; found {locality_rows}")

    header_row = locality_rows[0]
    header_values = raw.iloc[header_row]
    year_columns = []
    for column, value in header_values.items():
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        if pd.notna(numeric) and int(numeric) == VGV_SOURCE_YEAR:
            year_columns.append(column)
    if len(year_columns) != 1:
        raise ValueError(
            f"Expected one {VGV_SOURCE_YEAR} column in {path.name}; found {year_columns}"
        )

    price_column = year_columns[0]
    marker_column = price_column + 1 if price_column + 1 < raw.shape[1] else None

    result = pd.DataFrame(
        {
            "vgv_locality": raw.iloc[header_row + 1 :, 0].astype("string").str.strip(),
            "acquisition_median_2025_aud": pd.to_numeric(
                raw.iloc[header_row + 1 :, price_column], errors="coerce"
            ),
        }
    )
    if marker_column is not None:
        result["vgv_source_marker_2025"] = (
            raw.iloc[header_row + 1 :, marker_column].astype("string").str.strip()
        )
    else:
        result["vgv_source_marker_2025"] = pd.NA

    result = result.loc[
        result["vgv_locality"].notna()
        & result["acquisition_median_2025_aud"].gt(0)
    ].copy()
    result["suburb_key"] = result["vgv_locality"].map(normalise_suburb)
    result["dwelling_class"] = dwelling_class
    result["acquisition_price_source_year"] = VGV_SOURCE_YEAR
    result["acquisition_price_source_file"] = path.name
    result["acquisition_price_source_url"] = VGV_SOURCE_URL

    duplicate_keys = result.duplicated(["suburb_key", "dwelling_class"], keep=False)
    if duplicate_keys.any():
        duplicates = result.loc[
            duplicate_keys, ["vgv_locality", "suburb_key", "dwelling_class"]
        ]
        raise ValueError(f"Duplicate VGV join keys found:\n{duplicates.to_string(index=False)}")

    return result.reset_index(drop=True)


def read_dffh_bedroom_rents(path: str | Path) -> pd.DataFrame:
    """Read valid September 2025 moving-annual rent rows from the DFFH workbook."""
    path = Path(path)
    frames: list[pd.DataFrame] = []

    for sheet_name, (dwelling_class, bedrooms) in DFFH_WORKSHEETS.items():
        raw = pd.read_excel(path, sheet_name=sheet_name, header=None)
        period_headers = raw.iloc[1].astype("string").str.strip()
        period_columns = period_headers[
            period_headers.eq(DFFH_SOURCE_PERIOD)
        ].index.tolist()
        count_columns = [
            column
            for column in period_columns
            if str(raw.iloc[2, column]).strip().casefold() == "count"
        ]
        median_columns = [
            column
            for column in period_columns
            if str(raw.iloc[2, column]).strip().casefold() == "median"
        ]
        if len(count_columns) != 1 or len(median_columns) != 1:
            raise ValueError(
                f"Could not uniquely identify {DFFH_SOURCE_PERIOD} count and median "
                f"columns in sheet {sheet_name!r}: "
                f"count={count_columns}, median={median_columns}"
            )

        sheet = pd.DataFrame(
            {
                "dffh_region": raw.iloc[3:, 0].ffill().astype("string").str.strip(),
                "dffh_market": raw.iloc[3:, 1].astype("string").str.strip(),
                "dffh_lettings_count": pd.to_numeric(
                    raw.iloc[3:, count_columns[0]], errors="coerce"
                ),
                "dffh_median_weekly_rent_aud": pd.to_numeric(
                    raw.iloc[3:, median_columns[0]], errors="coerce"
                ),
            }
        )
        sheet["dwelling_class"] = dwelling_class
        sheet["dffh_bedroom_category"] = bedrooms
        frames.append(sheet)

    result = pd.concat(frames, ignore_index=True)
    result = result.loc[
        result["dffh_market"].notna()
        & result["dffh_market"].ne("Group Total")
        & result["dffh_lettings_count"].gt(0)
        & result["dffh_median_weekly_rent_aud"].gt(0)
    ].copy()
    result["dffh_source_period"] = DFFH_SOURCE_PERIOD
    result["dffh_source_file"] = path.name
    result["dffh_source_url"] = DFFH_SOURCE_URL

    keys = ["dffh_market", "dwelling_class", "dffh_bedroom_category"]
    duplicate_keys = result.duplicated(keys, keep=False)
    if duplicate_keys.any():
        duplicates = result.loc[duplicate_keys, keys + ["dffh_region"]]
        raise ValueError(
            "Duplicate DFFH market/class/bedroom rows found:\n"
            f"{duplicates.to_string(index=False)}"
        )
    return result.sort_values(keys).reset_index(drop=True)


def _weighted_median(values: pd.Series, weights: pd.Series) -> float:
    """Select the first sorted rent reaching half the positive letting count.

    Inputs are category medians, not individual lease rents. An exact half-way
    tie selects the lower rent rather than averaging the two category medians.
    """
    valid = pd.DataFrame({"value": values, "weight": weights}).dropna()
    valid = valid.loc[valid["weight"].gt(0)].sort_values("value")
    if valid.empty:
        return np.nan
    cutoff = valid["weight"].sum() / 2
    return float(valid.loc[valid["weight"].cumsum().ge(cutoff), "value"].iloc[0])


def build_dffh_representative_rents(dffh_rents: pd.DataFrame) -> pd.DataFrame:
    """Build a letting-count-weighted median of category rents per market/class."""
    rows = []
    for (market, dwelling_class), group in dffh_rents.groupby(
        ["dffh_market", "dwelling_class"], observed=True, sort=True
    ):
        weights = group["dffh_lettings_count"]
        rents = group["dffh_median_weekly_rent_aud"]
        rows.append(
            {
                "dffh_market": market,
                "dwelling_class": dwelling_class,
                "dffh_representative_weekly_rent_aud": _weighted_median(
                    rents, weights
                ),
                "dffh_weighted_mean_weekly_rent_aud": float(
                    np.average(rents, weights=weights)
                ),
                "dffh_representative_lettings_count": int(weights.sum()),
                "dffh_bedroom_categories_available": int(
                    group["dffh_bedroom_category"].nunique()
                ),
                "dffh_available_bedroom_categories": ", ".join(
                    str(value)
                    for value in sorted(group["dffh_bedroom_category"].unique())
                ),
                "dffh_representative_rent_method": (
                    "count-weighted median of bedroom-category median rents"
                ),
            }
        )
    return pd.DataFrame(rows)


# 3. Match rental markets and calculate the bedroom-adjusted acquisition proxy.
def build_dffh_suburb_crosswalk(
    dffh_rents: pd.DataFrame,
    listing_suburbs: Iterable[object],
    listing_lga_by_suburb_key: Mapping[str, str] | None = None,
) -> pd.DataFrame:
    """Map listing localities to the most specific supported DFFH market.

    Explicit suburb or grouped-market matches are preferred. When DFFH does not
    publish the locality separately, an unambiguous listing suburb-to-LGA value
    may be used as a broader fallback if that LGA is itself a DFFH market. This
    prevents regional localities such as Healesville and Warburton from being
    silently excluded while retaining the lower geographic precision in the
    mapping method and priority fields.
    """
    known = pd.DataFrame({"listing_suburb": pd.Series(list(listing_suburbs))})
    known = known.dropna().drop_duplicates().copy()
    known["suburb_key"] = known["listing_suburb"].map(normalise_suburb)
    known = known.dropna(subset=["suburb_key"])
    known_by_key = dict(zip(known["suburb_key"], known["listing_suburb"]))

    candidates = []
    for market in sorted(dffh_rents["dffh_market"].dropna().unique()):
        full_key = normalise_suburb(market)
        pieces = [(full_key, "exact DFFH market name", 1)]
        pieces.extend(
            (normalise_suburb(part), "named component of grouped DFFH market", 2)
            for part in str(market).split("-")
        )

        for source_key, method, priority in pieces:
            if pd.isna(source_key):
                continue
            target_key = source_key
            candidate_method = method
            candidate_priority = priority
            if source_key not in known_by_key and source_key in DFFH_LOCALITY_ALIASES:
                target_key = DFFH_LOCALITY_ALIASES[source_key]
                candidate_method = "unambiguous DFFH locality-name alias"
                candidate_priority = 3
            if target_key in known_by_key:
                candidates.append(
                    {
                        "suburb_key": target_key,
                        "dffh_market": market,
                        "dffh_mapping_method": candidate_method,
                        "dffh_match_priority": candidate_priority,
                    }
                )

    candidate_frame = pd.DataFrame(
        candidates,
        columns=[
            "suburb_key", "dffh_market", "dffh_mapping_method", "dffh_match_priority"
        ],
    )
    if not candidate_frame.empty:
        candidate_frame = (
            candidate_frame.sort_values(
                ["suburb_key", "dffh_match_priority", "dffh_market"]
            )
            .drop_duplicates("suburb_key", keep="first")
        )

    crosswalk = known.merge(candidate_frame, on="suburb_key", how="left")
    if listing_lga_by_suburb_key:
        market_by_key = {
            normalise_suburb(market): market
            for market in sorted(dffh_rents["dffh_market"].dropna().unique())
        }
        crosswalk["listing_lga"] = crosswalk["suburb_key"].map(
            listing_lga_by_suburb_key
        )
        fallback_market = crosswalk["listing_lga"].map(
            lambda value: market_by_key.get(normalise_suburb(value))
            if pd.notna(value)
            else np.nan
        )
        fallback = crosswalk["dffh_market"].isna() & fallback_market.notna()
        crosswalk.loc[fallback, "dffh_market"] = fallback_market.loc[fallback]
        crosswalk.loc[fallback, "dffh_mapping_method"] = (
            "LGA-level DFFH fallback from neighbourhood_cleansed"
        )
        crosswalk.loc[fallback, "dffh_match_priority"] = 4

    crosswalk["dffh_mapping_method"] = crosswalk[
        "dffh_mapping_method"
    ].fillna("not matched to an explicitly named DFFH market")
    return crosswalk.sort_values("listing_suburb").reset_index(drop=True)


def build_bedroom_adjusted_acquisition_proxy(
    listings: pd.DataFrame,
    dffh_workbook: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Add a rent-ratio bedroom adjustment to the unadjusted VGV median.

    The adjustment assumes approximately constant gross long-term rental yield
    within each DFFH market and dwelling class. It is a modelling proxy, not an
    observed bedroom-specific acquisition price.
    """
    required = {
        "id",
        "suburb",
        "suburb_key",
        "dwelling_class",
        "bedrooms",
        "acquisition_median_2025_aud",
    }
    missing = sorted(required.difference(listings.columns))
    if missing:
        raise KeyError(
            "Run build_property_price_merge first; required columns are missing: "
            f"{missing}"
        )

    result = listings.copy()
    dffh_rents = read_dffh_bedroom_rents(dffh_workbook)
    representative = build_dffh_representative_rents(dffh_rents)
    dffh_rents = dffh_rents.merge(
        representative,
        on=["dffh_market", "dwelling_class"],
        how="left",
        validate="many_to_one",
    )
    listing_lga_by_suburb_key: dict[str, str] = {}
    if "neighbourhood_cleansed" in result.columns:
        suburb_lga = (
            result.loc[
                result["suburb_key"].notna()
                & result["neighbourhood_cleansed"].notna(),
                ["suburb_key", "neighbourhood_cleansed"],
            ]
            .drop_duplicates()
        )
        unambiguous = suburb_lga.groupby("suburb_key")[
            "neighbourhood_cleansed"
        ].transform("nunique").eq(1)
        suburb_lga = suburb_lga.loc[unambiguous].drop_duplicates("suburb_key")
        listing_lga_by_suburb_key = dict(
            zip(suburb_lga["suburb_key"], suburb_lga["neighbourhood_cleansed"])
        )

    crosswalk = build_dffh_suburb_crosswalk(
        dffh_rents,
        result["suburb"].dropna().unique(),
        listing_lga_by_suburb_key=listing_lga_by_suburb_key,
    )

    result = result.merge(
        crosswalk[
            [
                "suburb_key",
                "dffh_market",
                "dffh_mapping_method",
                "dffh_match_priority",
            ]
        ],
        on="suburb_key",
        how="left",
        validate="many_to_one",
    )

    bedroom_numeric = pd.to_numeric(result["bedrooms"], errors="coerce")
    bedroom_integer = bedroom_numeric.round()
    is_integer = bedroom_numeric.notna() & np.isclose(
        bedroom_numeric, bedroom_integer, atol=1e-9
    )
    result["dffh_bedroom_category"] = pd.Series(
        np.where(is_integer, bedroom_integer, np.nan), index=result.index
    ).astype("Int64")

    rent_columns = [
        "dffh_market",
        "dwelling_class",
        "dffh_bedroom_category",
        "dffh_region",
        "dffh_lettings_count",
        "dffh_median_weekly_rent_aud",
        "dffh_representative_weekly_rent_aud",
        "dffh_weighted_mean_weekly_rent_aud",
        "dffh_representative_lettings_count",
        "dffh_bedroom_categories_available",
        "dffh_available_bedroom_categories",
        "dffh_representative_rent_method",
        "dffh_source_period",
        "dffh_source_file",
        "dffh_source_url",
    ]
    result = result.merge(
        dffh_rents[rent_columns],
        on=["dffh_market", "dwelling_class", "dffh_bedroom_category"],
        how="left",
        validate="many_to_one",
    )

    supported_category = (
        result["dwelling_class"].eq("Unit")
        & result["dffh_bedroom_category"].isin([1, 2, 3])
    ) | (
        result["dwelling_class"].eq("House")
        & result["dffh_bedroom_category"].isin([2, 3, 4])
    )
    sufficient_categories = result["dffh_bedroom_categories_available"].ge(2)
    adjustment_available = (
        result["acquisition_median_2025_aud"].gt(0)
        & result["dffh_median_weekly_rent_aud"].gt(0)
        & result["dffh_representative_weekly_rent_aud"].gt(0)
        & sufficient_categories
    )

    result["bedroom_rent_adjustment_factor"] = np.where(
        adjustment_available,
        result["dffh_median_weekly_rent_aud"]
        / result["dffh_representative_weekly_rent_aud"],
        np.nan,
    )
    result["bedroom_adjusted_acquisition_price_proxy_aud"] = np.where(
        adjustment_available,
        result["acquisition_median_2025_aud"]
        * result["bedroom_rent_adjustment_factor"],
        np.nan,
    )

    result["bedroom_adjustment_status"] = np.select(
        [
            ~result["dwelling_class"].isin(["House", "Unit"]),
            result["acquisition_median_2025_aud"].isna(),
            ~supported_category,
            result["dffh_market"].isna(),
            result["dffh_median_weekly_rent_aud"].isna(),
            ~sufficient_categories.fillna(False),
            adjustment_available,
        ],
        [
            "unclassified dwelling type",
            "VGV acquisition median unavailable",
            "bedroom count outside DFFH categories",
            "suburb/LGA not matched to a published DFFH market",
            "DFFH bedroom-specific rent unavailable",
            "fewer than two DFFH bedroom categories available",
            "bedroom-adjusted acquisition proxy available",
        ],
        default="adjustment unavailable",
    )

    if "estimated_revenue_l365d" in result.columns:
        annual_revenue = pd.to_numeric(result["estimated_revenue_l365d"], errors="coerce")
        result["bedroom_adjusted_estimated_gross_revenue_yield_pct"] = np.where(
            annual_revenue.gt(0)
            & result["bedroom_adjusted_acquisition_price_proxy_aud"].gt(0),
            annual_revenue
            / result["bedroom_adjusted_acquisition_price_proxy_aud"]
            * 100,
            np.nan,
        )
    else:
        result["bedroom_adjusted_estimated_gross_revenue_yield_pct"] = np.nan

    status_counts = result["bedroom_adjustment_status"].value_counts(dropna=False)
    diagnostics_rows = [
        ("input_listings", len(result)),
        ("listings_in_supported_DFFH_bedroom_categories", int(supported_category.sum())),
        ("listings_with_DFFH_market_match", int(result["dffh_market"].notna().sum())),
        (
            "listings_with_DFFH_bedroom_rent",
            int(result["dffh_median_weekly_rent_aud"].notna().sum()),
        ),
        (
            "listings_with_bedroom_adjusted_acquisition_proxy",
            int(adjustment_available.sum()),
        ),
        (
            "listings_with_bedroom_adjusted_gross_yield_proxy",
            int(
                result["bedroom_adjusted_estimated_gross_revenue_yield_pct"]
                .notna()
                .sum()
            ),
        ),
    ]
    diagnostics_rows.extend(
        (f"status: {status}", int(count)) for status, count in status_counts.items()
    )
    diagnostics = pd.DataFrame(diagnostics_rows, columns=["metric", "value"])
    return result, dffh_rents, crosswalk, diagnostics


# 4. Merge VGV medians and retain separate Airbnb nightly-price comparisons.
def _aggregate_price(
    frame: pd.DataFrame,
    keys: Iterable[str],
    prefix: str,
) -> pd.DataFrame:
    return (
        frame.groupby(list(keys), dropna=False, observed=True)
        .agg(
            **{
                f"{prefix}_listings": ("id", "size"),
                f"{prefix}_mean_nightly_price_aud": ("price", "mean"),
                f"{prefix}_median_nightly_price_aud": ("price", "median"),
            }
        )
        .reset_index()
    )


def build_property_price_merge(
    listings: pd.DataFrame,
    house_workbook: str | Path,
    unit_workbook: str | Path,
    minimum_reliable_peer_group: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return listing-level results, tidy VGV data, exact peers and diagnostics.

    Nightly-price peer groups do not enter the VGV purchase-price calculation.
    All joins are many-to-one and must retain one row per input listing.
    """
    required = {
        "id",
        "suburb",
        "property_type",
        "bedrooms",
        "bathrooms_n",
        "price",
    }
    missing = sorted(required.difference(listings.columns))
    if missing:
        raise KeyError(f"Listings data is missing required columns: {missing}")
    if listings["id"].isna().any() or listings["id"].astype("string").duplicated().any():
        raise ValueError("Input listings must have non-missing, unique listing IDs.")
    if minimum_reliable_peer_group < 1:
        raise ValueError("The nightly-price peer threshold must be at least one.")

    result = listings.copy()
    result["id"] = result["id"].astype("string")
    result["price"] = pd.to_numeric(result["price"], errors="coerce")
    result["suburb_key"] = result["suburb"].map(normalise_suburb)
    result["dwelling_class"] = result["property_type"].map(classify_dwelling)

    # Values are retained at the half-unit precision available in the Airbnb data.
    result["bedrooms_benchmark"] = (
        pd.to_numeric(result["bedrooms"], errors="coerce").mul(2).round().div(2)
    )
    result["bathrooms_benchmark"] = (
        pd.to_numeric(result["bathrooms_n"], errors="coerce").mul(2).round().div(2)
    )

    valid_price = result["price"].gt(0) & result["price"].notna()
    peer_source = result.loc[valid_price].copy()

    exact_keys = [
        "suburb_key",
        "dwelling_class",
        "bedrooms_benchmark",
        "bathrooms_benchmark",
    ]
    exact_peers = _aggregate_price(peer_source, exact_keys, "exact_peer")
    result = result.merge(exact_peers, on=exact_keys, how="left", validate="many_to_one")

    market_exact_keys = [
        "dwelling_class",
        "bedrooms_benchmark",
        "bathrooms_benchmark",
    ]
    market_exact = _aggregate_price(peer_source, market_exact_keys, "market_bed_bath_peer")
    result = result.merge(
        market_exact,
        on=market_exact_keys,
        how="left",
        validate="many_to_one",
    )

    local_class_keys = ["suburb_key", "dwelling_class"]
    local_class = _aggregate_price(peer_source, local_class_keys, "suburb_class_peer")
    result = result.merge(
        local_class,
        on=local_class_keys,
        how="left",
        validate="many_to_one",
    )

    market_class_keys = ["dwelling_class"]
    market_class = _aggregate_price(peer_source, market_class_keys, "market_class_peer")
    result = result.merge(
        market_class,
        on=market_class_keys,
        how="left",
        validate="many_to_one",
    )

    exact_ok = result["exact_peer_listings"].ge(minimum_reliable_peer_group)
    market_exact_ok = result["market_bed_bath_peer_listings"].ge(
        minimum_reliable_peer_group
    )
    local_class_ok = result["suburb_class_peer_listings"].ge(
        minimum_reliable_peer_group
    )

    result["recommended_peer_benchmark_level"] = np.select(
        [exact_ok, market_exact_ok, local_class_ok],
        [
            "suburb + dwelling class + bedrooms + bathrooms",
            "all suburbs + dwelling class + bedrooms + bathrooms",
            "suburb + dwelling class",
        ],
        default="all suburbs + dwelling class",
    )

    def select_recommended(statistic: str) -> pd.Series:
        return pd.Series(
            np.select(
                [exact_ok, market_exact_ok, local_class_ok],
                [
                    result[f"exact_peer_{statistic}_nightly_price_aud"],
                    result[f"market_bed_bath_peer_{statistic}_nightly_price_aud"],
                    result[f"suburb_class_peer_{statistic}_nightly_price_aud"],
                ],
                default=result[f"market_class_peer_{statistic}_nightly_price_aud"],
            ),
            index=result.index,
        )

    result["recommended_peer_mean_nightly_price_aud"] = select_recommended("mean")
    result["recommended_peer_median_nightly_price_aud"] = select_recommended("median")
    result["recommended_peer_listings"] = np.select(
        [exact_ok, market_exact_ok, local_class_ok],
        [
            result["exact_peer_listings"],
            result["market_bed_bath_peer_listings"],
            result["suburb_class_peer_listings"],
        ],
        default=result["market_class_peer_listings"],
    )

    vgv_benchmarks = pd.concat(
        [
            read_vgv_annual_medians(house_workbook, "House"),
            read_vgv_annual_medians(unit_workbook, "Unit"),
        ],
        ignore_index=True,
    )
    result = result.merge(
        vgv_benchmarks,
        on=["suburb_key", "dwelling_class"],
        how="left",
        validate="many_to_one",
    )

    if "estimated_revenue_l365d" in result.columns:
        annual_revenue = pd.to_numeric(result["estimated_revenue_l365d"], errors="coerce")
        result["estimated_gross_revenue_yield_pct"] = np.where(
            annual_revenue.gt(0) & result["acquisition_median_2025_aud"].gt(0),
            annual_revenue / result["acquisition_median_2025_aud"] * 100,
            np.nan,
        )
    else:
        result["estimated_gross_revenue_yield_pct"] = np.nan

    classified = result["dwelling_class"].isin(["House", "Unit"])
    acquisition_matched = result["acquisition_median_2025_aud"].notna()
    diagnostics = pd.DataFrame(
        {
            "metric": [
                "input_listings",
                "classified_as_house",
                "classified_as_unit",
                "unclassified_property_type",
                "classified_listings_with_vgv_median",
                "classified_listings_without_vgv_median",
                "all_listings_with_vgv_median",
                "listings_with_exact_local_peer_group_n_ge_threshold",
                "minimum_reliable_peer_group",
            ],
            "value": [
                len(result),
                result["dwelling_class"].eq("House").sum(),
                result["dwelling_class"].eq("Unit").sum(),
                result["dwelling_class"].eq("Unclassified").sum(),
                (classified & acquisition_matched).sum(),
                (classified & ~acquisition_matched).sum(),
                acquisition_matched.sum(),
                exact_ok.sum(),
                minimum_reliable_peer_group,
            ],
        }
    )

    return result, vgv_benchmarks, exact_peers, diagnostics


# 5. Attach readable references and export the main CSV and audit tables.
def add_source_references(frame: pd.DataFrame) -> pd.DataFrame:
    """Add source labels without changing existing fields or numerical values.

    Government references are populated only where their source rows matched.
    Source URLs, source periods and workbook filenames remain in their existing
    columns. No notes are inserted above the CSV header, so pd.read_csv still
    reads the output directly. The companion notebook uses this same helper.
    """
    result = frame.copy()
    result["listings_source_reference"] = LISTINGS_SOURCE_REFERENCE
    if "acquisition_price_source_file" in result.columns:
        matched = result["acquisition_price_source_file"].notna()
        result["acquisition_price_source_reference"] = (
            result["dwelling_class"].map(VGV_SOURCE_REFERENCES).where(matched, pd.NA)
        )
    if "dffh_source_file" in result.columns:
        result["dffh_source_reference"] = pd.Series(
            DFFH_SOURCE_REFERENCE, index=result.index, dtype="string"
        ).where(result["dffh_source_file"].notna(), pd.NA)
    return result


def preview_columns(frame: pd.DataFrame) -> list[str]:
    """Choose the smaller, human-readable audit preview without altering the CSV."""
    candidates = [
        "id",
        "suburb",
        "property_type",
        "dwelling_class",
        "bedrooms",
        "bathrooms_n",
        "price",
        "exact_peer_listings",
        "exact_peer_mean_nightly_price_aud",
        "exact_peer_median_nightly_price_aud",
        "recommended_peer_benchmark_level",
        "recommended_peer_listings",
        "recommended_peer_mean_nightly_price_aud",
        "recommended_peer_median_nightly_price_aud",
        "acquisition_median_2025_aud",
        "vgv_source_marker_2025",
        "dffh_market",
        "dffh_mapping_method",
        "dffh_bedroom_category",
        "dffh_lettings_count",
        "dffh_median_weekly_rent_aud",
        "dffh_representative_weekly_rent_aud",
        "dffh_bedroom_categories_available",
        "bedroom_rent_adjustment_factor",
        "bedroom_adjusted_acquisition_price_proxy_aud",
        "bedroom_adjustment_status",
        "estimated_revenue_l365d",
        "estimated_gross_revenue_yield_pct",
        "bedroom_adjusted_estimated_gross_revenue_yield_pct",
        "listings_source_reference",
        "acquisition_price_source_reference",
        "acquisition_price_source_year",
        "acquisition_price_source_file",
        "acquisition_price_source_url",
        "dffh_source_reference",
        "dffh_source_period",
        "dffh_source_file",
        "dffh_source_url",
    ]
    return [column for column in candidates if column in frame.columns]


def save_merge_outputs(
    result: pd.DataFrame,
    vgv_benchmarks: pd.DataFrame,
    exact_peers: pd.DataFrame,
    diagnostics: pd.DataFrame,
    output_directory: str | Path,
    preview_rows: int = 500,
    dffh_rents: pd.DataFrame | None = None,
    dffh_crosswalk: pd.DataFrame | None = None,
    bedroom_adjustment_diagnostics: pd.DataFrame | None = None,
    audit_directory: str | Path | None = None,
) -> dict[str, Path]:
    """Save the full CSV and optional audit tables, preserving all input rows.

    audit_directory defaults to output_directory for existing callers. Existing
    files with these exact output names are replaced; input files are not edited.
    """
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    audit_directory = (
        Path(audit_directory) if audit_directory is not None else output_directory
    )
    audit_directory.mkdir(parents=True, exist_ok=True)
    result = add_source_references(result)

    paths = {
        "full": output_directory / "listings_with_property_price_benchmarks.csv",
        "preview": audit_directory / "listing_property_price_merge_preview.csv",
        "vgv_tidy": audit_directory / "vgv_acquisition_medians_2025_tidy.csv",
        "peer_groups": audit_directory / "airbnb_nightly_price_peer_benchmarks.csv",
        "diagnostics": audit_directory / "property_price_merge_diagnostics.csv",
    }

    result.to_csv(paths["full"], index=False)
    (
        result.sort_values(
            ["suburb", "dwelling_class", "bedrooms_benchmark", "bathrooms_benchmark", "id"],
            na_position="last",
        )
        .loc[:, preview_columns(result)]
        .head(preview_rows)
        .to_csv(paths["preview"], index=False)
    )
    vgv_benchmarks.to_csv(paths["vgv_tidy"], index=False)
    exact_peers.to_csv(paths["peer_groups"], index=False)
    diagnostics.to_csv(paths["diagnostics"], index=False)

    if dffh_rents is not None:
        paths["dffh_rents"] = (
            audit_directory / "dffh_bedroom_rents_September_2025_tidy.csv"
        )
        dffh_rents.to_csv(paths["dffh_rents"], index=False)
    if dffh_crosswalk is not None:
        paths["dffh_crosswalk"] = audit_directory / "dffh_suburb_crosswalk.csv"
        dffh_crosswalk.to_csv(paths["dffh_crosswalk"], index=False)
    if bedroom_adjustment_diagnostics is not None:
        paths["bedroom_adjustment_diagnostics"] = (
            audit_directory / "bedroom_adjustment_diagnostics.csv"
        )
        bedroom_adjustment_diagnostics.to_csv(
            paths["bedroom_adjustment_diagnostics"], index=False
        )
    return paths


def run_from_files(
    listings_csv: str | Path,
    house_workbook: str | Path,
    unit_workbook: str | Path,
    output_directory: str | Path,
    dffh_workbook: str | Path | None = None,
    audit_directory: str | Path | None = None,
) -> dict[str, Path]:
    """Run the documented local-file workflow; DFFH adds the bedroom adjustment."""
    listings = pd.read_csv(listings_csv, dtype={"id": "string"}, low_memory=False)
    result, vgv_benchmarks, exact_peers, diagnostics = build_property_price_merge(
        listings,
        house_workbook,
        unit_workbook,
    )
    dffh_rents = None
    dffh_crosswalk = None
    bedroom_adjustment_diagnostics = None
    if dffh_workbook is not None:
        (
            result,
            dffh_rents,
            dffh_crosswalk,
            bedroom_adjustment_diagnostics,
        ) = build_bedroom_adjusted_acquisition_proxy(result, dffh_workbook)
    return save_merge_outputs(
        result,
        vgv_benchmarks,
        exact_peers,
        diagnostics,
        output_directory,
        dffh_rents=dffh_rents,
        dffh_crosswalk=dffh_crosswalk,
        bedroom_adjustment_diagnostics=bedroom_adjustment_diagnostics,
        audit_directory=audit_directory,
    )


# 6. Command-line entry point. Importing this module does not read or write files.
def main() -> None:
    """Parse local input/output paths and print the files actually written."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Merge cleaned Airbnb listings with VGV sale and DFFH rent data.",
        epilog="See the module docstring for the formula, assumptions and source references.",
    )
    parser.add_argument("listings_csv", type=Path, help="Cleaned, suburb-assigned listing CSV.")
    parser.add_argument("house_workbook", type=Path, help="VGV Houses by suburb 2015-2025.")
    parser.add_argument("unit_workbook", type=Path, help="VGV Units by suburb 2015-2025.")
    parser.add_argument("output_directory", type=Path, help="Directory for the full CSV.")
    parser.add_argument(
        "--dffh-workbook", type=Path,
        help="September 2025 moving-annual rent workbook; needed for the bedroom proxy.",
    )
    parser.add_argument(
        "--audit-directory", type=Path,
        help="Directory for support tables; defaults to the full CSV output directory.",
    )
    arguments = parser.parse_args()

    written = run_from_files(
        arguments.listings_csv,
        arguments.house_workbook,
        arguments.unit_workbook,
        arguments.output_directory,
        arguments.dffh_workbook,
        audit_directory=arguments.audit_directory,
    )
    for label, path in written.items():
        print(f"{label}: {path}")


if __name__ == "__main__":
    main()
