# CMCE30005 Business Analytics Challenge
## Group 6 — Melbourne Airbnb Revenue and Investment Analysis

**Subject:** CMCE30005 Business Analytics Challenge, Semester 2 2026  
**University:** University of Melbourne  
**Team members:** Leon Li, Yuvrraj Puruhit, Jiayi Zhang and Chenfei Jin

This project supports a prospective Melbourne short-stay host by identifying listing locations and property formats associated with stronger demand and estimated annual revenue. Acquisition-cost and gross-yield work is in development; the project cannot yet estimate true return on investment (ROI).

---

## Business Problem

### Introduction

Location, dwelling format, stay policy and guest experience can influence Airbnb performance. Recommendations should distinguish market opportunity from weak evidence, compare like-for-like listings and recognise acquisition and operating costs.

The current primary question is:

> **Which Melbourne suburb and client-facing property format have the strongest statistically supported estimated annual Airbnb revenue for a prospective host?**

The final report is also intended to investigate:

- whether estimated acquisition costs change the ranking when expressed as gross revenue yield;
- which amenities have the strongest revenue association relative to their installation cost;
- which minimum-night policy is most appropriate; and
- which of the six component review scores—accuracy, cleanliness, check-in, communication, location and value—has the strongest association with estimated revenue.

These extensions are work in progress, not completed yet.

Victoria treats a stay of less than 28 consecutive days as a short stay and applies a 7.5% levy to applicable total booking fees. This makes it important to distinguish gross revenue potential from investment profitability.

---

## Dataset

The project uses an Inside Airbnb Melbourne snapshot scraped mainly during June 2026, plus official Victorian geography and preliminary property-market inputs.

| File | Unit of observation | Important content |
|---|---|---|
| `listings_airbnb.csv` | One Airbnb listing | Host, location, property type, capacity, price, amenities, review scores and modelled performance |
| `reviews_airbnb.csv` | One review | Listing ID, review ID and review date |
| `calendar_airbnb.csv` | One listing-date | Date, availability and minimum/maximum-night rules |
| `vic_suburbs.geojson` | One Victorian locality polygon | Official locality name and geometry used for point-in-polygon suburb assignment |
| `Testing/VGV_*_by_suburb_2015-2025.xlsx` | One locality-year/class benchmark | VGV suburb-level house and unit sale-price medians |
| `Testing/DFFH_moving_annual_rent_by_suburb_September_2025.xlsx` | One rental market, dwelling class and bedroom category | DFFH letting counts and median weekly rents used in acquisition-proxy research |

The fresh notebook run loaded 25,728 listings, 1,026,690 reviews and 9,390,720 calendar rows. Listing and review files connect through listing IDs; all IDs are imported as strings to avoid precision loss. Raw files are kept unchanged and are separate from cleaned modelling data.

---

## Data Processing and Methodology

Major processing decisions are explained in `Group6_cleaning_stratifled _regression_2.0.ipynb`:

1. Currency prices become numeric; missing or non-positive prices are excluded.
2. Dates are parsed first. Review windows use each listing's scrape date.
3. Scope requires `room_type = Entire home/apt`, a review in the previous 12 months and a calendar date permitting a stay below 28 nights.
4. Missing property fields are flagged and handled within capacity groups; 18 rows missing both bedrooms and beds are removed.
5. Coordinates are spatially joined to locality polygons; six cleaned listings remain `UNKNOWN`.
6. Right-skewed price and revenue are log-transformed. Inference clusters by host and applies Benjamini–Hochberg correction where required.

After the principal filters, 11,744 listings remain; 11,726 remain after unusable property attributes are removed. The mainstream modelling sample contains 11,545 listings after separating the extreme luxury-price tail.

### Supported suburb × property-format model

`room_type` describes whether guests receive the whole space; it does not establish the physical building type. The notebook therefore retains Airbnb's raw `property_type` and creates transparent client-facing formats: whole house, whole apartment/unit, whole townhouse, whole guesthouse/secondary dwelling and specialty/other accommodation.

An exact suburb × format enters the recommendation model only with at least 10 listings from at least 8 hosts. A primary recommendation additionally requires at least 20 listings, 10 hosts, a positive cluster-robust confidence interval and an FDR-adjusted q-value below 0.05. The unified model controls for capacity, bedrooms, bathrooms, minimum nights and host characteristics. An 80/20 host-grouped split tests performance on hosts not used for training.

The fresh run identifies **Fitzroy × whole apartment/unit** as the leading strong-evidence candidate for a standard new-host scenario. It has 113 listings across 82 hosts, adjusted estimated annual revenue of **$26,099** and a 95% confidence interval of **$21,544–$31,618** (`q = 2.745 × 10⁻¹⁰`). This is modelled gross revenue, not income or investment return. Held-out performance is moderate (`R² = 0.244`; MAE about `$17,231`).

The previously highlighted Gruyere guesthouse combination has only two exact observations and is now labelled exploratory rather than used as the primary recommendation.

---

## Analysis Completed and Work in Progress

Completed work includes data-quality investigation, price and recent-review distributions, dynamic calendar stay-policy construction, review-based occupancy sensitivity measures, suburb allocation, controlled price/revenue models, amenity association modelling and the supported suburb × property-format screen.

The following work is unfinished:

- **Acquisition cost and return:** VGV medians and DFFH bedroom rents are being evaluated as a bedroom-adjusted acquisition-price proxy. VGV data is broad suburb × house/unit data, not a property valuation. Any resulting ratio will be called estimated gross revenue yield, not ROI.
- **Amenity benefit versus cost:** associations are available, but installation-cost data or transparent cost bands must be sourced before recommending the best revenue effect per dollar spent.
- **Minimum nights:** preliminary policy summaries exist, but controlled comparisons and two-, three-, five- and seven-night sensitivity scenarios remain to be completed.
- **Review scores:** six component scores will be compared using correlation, controlled modelling and multicollinearity checks. No component is yet declared most important.
- **Seasonality:** calendar month/season patterns and location × season interactions remain planned.

---

## Assumptions and Limitations

- Occupancy and revenue fields are modelled estimates, not transactions.
- Reviews are an imperfect proxy; sensitivity analysis assumes a 50% review rate and a three-night baseline where a higher minimum does not apply.
- Unavailable calendar dates may be booked or host-blocked.
- Quoted prices are snapshots and may not represent realised seasonal prices.
- Airbnb coordinates may be anonymised, and property types are host-reported rather than legal classifications.
- The model explains a limited share of held-out revenue variation.
- Estimated revenue excludes acquisition costs, financing, levy, tax, strata/body-corporate fees, cleaning, maintenance, utilities and management costs.
- True ROI requires observed acquisition and operating-cost data. Association and correlation do not establish causation.

---

## Repository Structure and Reproducibility

| Path | Purpose |
|---|---|
| `Group6_cleaning_stratifled _regression_2.0.ipynb` | Current main cleaning, modelling and recommendation workflow |
| `Testing/` | Preliminary property-price/rent merge, diagnostics and non-final acquisition-proxy outputs |
| `amenity_price_regression.csv` | Controlled quoted-price amenity associations from earlier exports |
| `amenity_revenue_decomposition.csv` | Amenity associations across price and review-derived activity components |
| Earlier `.ipynb` files | Development history; not the main reproducible workflow |

Required packages are `pandas`, `numpy`, `matplotlib`, `scipy`, `statsmodels`, `scikit-learn`, `geopandas`, `shapely` and `openpyxl`.

To reproduce the current result:

1. Place the three Airbnb CSV files and `vic_suburbs.geojson` beside the notebook.
2. Open the main notebook, restart the kernel and run every cell sequentially.
3. Confirm that all integrity checks and the host-grouped validation cell complete without errors.
4. Leave `EXPORT_CURRENT_RESULTS = False` unless refreshed recommendation tables are required.

Do not commit unnecessary generated files or very large raw data unless repository policy permits it.

---

## Project Status and Next Steps

The cleaning, suburb allocation, preliminary amenity models and evidence-supported revenue screen are operational. Next steps are to validate acquisition mappings, develop the gross-yield sensitivity analysis, add amenity cost estimates, complete minimum-stay and review-score models, test seasonality and convert supported results into final client recommendations.

Seasonality: We also plan to explore how seasonal demand may affect Airbnb revenue in Melbourne. As a popular tourist destination, Melbourne may experience changes in demand around holidays and major events. We aim to compare peak and off-peak periods and examine whether these patterns differ across suburbs. Our current calendar data can help explore availability patterns, although unavailable dates may include host-blocked nights. Additional monthly price and booking data would be needed to assess seasonal revenue differences more reliably.

Review scores: We plan to compare the relationship between estimated annual revenue and six review scores: accuracy, cleanliness, check-in, communication, location and value. We will first examine their correlations with revenue, then use regression to account for differences in location, property size and host characteristics. Since some scores are closely related, we will also check for multicollinearity. This analysis will help us understand which aspects of the guest experience are most strongly associated with revenue.

## Contribution Log

Entries before 18 September 2026 are **retrospectively reconstructed from group work and message history; they are not claimed to be Git commits**.

| Date | Member | Work completed | File/section |
|---|---|---|---|
| Before 18 Sep 2026 — retrospective | Group 6 | Data cleaning, review windows, stay-policy variables, suburb allocation and price/amenity modelling | Earlier notebooks; main notebook Sections 1–10 |
| 18 Sep 2026 | Group 6 | Replaced hard-coded recommendation multipliers with supported combinations, uncertainty checks and host-grouped validation; documented refined scope | Main notebook Sections 11–13; `README.md` |

This log should be updated regularly with the responsible member and relevant file or section.

---

## References

- [Inside Airbnb — data downloads](https://insideairbnb.com/get-the-data/)
- [Inside Airbnb — methodology and project information](https://insideairbnb.com/about/)
- [Victorian State Revenue Office — short-stay levy](https://sro.vic.gov.au/owning-property/short-stay-levy/understanding-short-stay-levy)
- [Valuer-General Victoria — property sales statistics](https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics)
- [Homes Victoria/DFFH — Rental Report](https://www.dffh.vic.gov.au/publications/rental-report)
- [DataVic — authoritative Victorian locality polygons](https://discover.data.vic.gov.au/dataset/vicmap-admin-locality-polygon-aligned-to-property)
- Benjamini, Y. and Hochberg, Y. (1995), “Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing.”

*Last updated: 18 September 2026.*
