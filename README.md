# CMCE30005 Business Analytics Challenge
## Group 6 — Melbourne Airbnb Investment Analysis

**Subject:** CMCE30005 Business Analytics Challenge, Semester 2 2026<br>
**University:** University of Melbourne<br>
**Team members:** Leon Li, Yuvrraj Puruhit, Jiayi Zhang and Chenfei Jin<br>
**Status:** Final analysis; this README supersedes the interim project description.<br>
**Main notebook:** [Group6_analysis_final.ipynb](Group6_analysis_final.ipynb)

## Executive summary

We recommend prioritising a **two-bedroom Collingwood apartment for property-level due diligence**, then considering a **two-bedroom Healesville house** to broaden seasonal demand exposure. These are screening recommendations, not instructions to purchase.

Collingwood's estimated annual gross revenue of **AUD 27,533**, divided by a **AUD 630,000 purchase-price proxy**, gives an estimated gross yield of **4.37%**, before operating costs. This is the highest yield among options meeting our minimum sample-size and statistical-evidence requirements. Fitzroy apartments lead the conservative revenue-only ranking, but their higher acquisition benchmark reduces estimated yield to **3.24%**.

Healesville houses have an estimated gross yield of **3.87%** and recorded **50.3% more winter reviews per listing on a 30-day scale** than Collingwood apartments in the following-year check. Combining equally weighted, normalised activity indices reduced variability by **40.6%** relative to Collingwood alone. This describes more balanced review activity, not a demonstrated reduction in property cash-flow risk.

Revenue is estimated, acquisition values are proxies and costs are excluded. Before committing capital, verify comparable sales, short-stay permissions, applicable levies and net operating returns.

## 1. Business problem and objectives

The client is considering multiple entire-property short-stay investments in the Melbourne market and surrounding study area. The analysis addresses five decisions:

1. Which suburb and property format offer the strongest evidence-supported estimated revenue?
2. How does acquisition cost change the shortlist when revenue is expressed as gross yield?
3. Can a second location complement the primary property's weaker seasonal activity?
4. Which amenities and minimum-stay policies warrant operational testing?
5. Which component guest ratings best predict overall guest experience?

The analysis distinguishes predicted revenue, estimated gross yield and net profitability. It does not optimise bedroom count, identify a particular property for purchase or estimate true return on investment.

## 2. Data sources and preparation

The Airbnb files are the project's June 2026 Melbourne snapshot. Government sales and rental inputs cover **2025**; their coverage period is not their publication or download date.

| Input | Records / coverage | Role |
|---|---|---|
| `listings_airbnb.csv` | 25,728 listings | Property characteristics, quoted prices, host information, review scores and supplied revenue estimates |
| `reviews_airbnb.csv` | 1,026,690 reviews | Dated review events for seasonal activity |
| `calendar_airbnb.csv` | 9,390,720 listing-date rows | Availability and date-specific stay rules |
| `vic_suburbs.geojson` | Victorian locality polygons | Spatial assignment of listings to suburbs |
| `Testing/VGV_houses_by_suburb_2015-2025.xlsx` | 2025 house medians used | Suburb-level house acquisition benchmarks |
| `Testing/VGV_units_by_suburb_2015-2025.xlsx` | 2025 unit medians used | Separate unit acquisition benchmarks |
| `Testing/DFFH_moving_annual_rent_by_suburb_September_2025.xlsx` | September 2025 moving-annual rents and letting counts | Bedroom adjustment within a matched rental market and dwelling class |
| `listings_with_property_price_benchmarks.csv` | 11,726 cleaned listings | Generated listing-level acquisition benchmarks, matching flags and source references |

Raw files remain unchanged. Listing and host IDs are read as strings to avoid precision loss.

### Cleaning and client scope

| Sequential step | Removed | Remaining |
|---|---:|---:|
| Raw listings | — | 25,728 |
| No recoverable positive price | 6,553 | 19,175 |
| Not an entire place | 4,703 | 14,472 |
| No review in the previous 12 months | 2,644 | 11,828 |
| No calendar date permitting a stay below 28 nights | 84 | 11,744 |
| Both bedroom and bed information missing | 18 | 11,726 |
| Quoted nightly price above AUD 1,000 | 181 | **11,545** |

The last filter defines the mainstream client scope; it does not classify expensive listings as errors. Eligible luxury observations are retained separately for sensitivity analysis.

Dates are parsed before constructing review windows. Calendar records capture changing minimum-stay rules, rather than assuming a listing's current minimum applies to every future date. Missing property attributes are flagged and filled using documented capacity-group and fallback rules.

Coordinates are joined to locality polygons. Six otherwise unmatched coastal points receive audited nearest-boundary assignments within a 500-metre safety threshold; more distant unmatched points stop the workflow. This resolves unmatched points but cannot eliminate suburb misclassification caused by Airbnb's location anonymisation.

## 3. Analytical approach

### 3.1 Revenue estimation and like-for-like comparisons

The recommendation model's dependent variable is **the log of Inside Airbnb's supplied `estimated_revenue_l365d`**. It is not observed transaction revenue and is not calculated by our regression from review counts.

A separate review-based revenue proxy is reconstructed for sensitivity and amenity cross-checks:

```text
Review-revenue proxy
  = nightly price
  × min[(reviews in the last 12 months ÷ 0.5)
        × max(minimum nights, 3), 255.5]
```

The proxy assumes a 50% review rate, a three-night stay baseline or a higher listing minimum, and a 70% annual occupancy cap. These provide a transparent approximation; they should not be described as an exact reconstruction of every supplied Inside Airbnb revenue value.

The main regression accounts for:

- suburb × client-facing property format;
- guest capacity, bedrooms and bathrooms;
- minimum nights and its missing-value indicator;
- Superhost status and host listing count.

Guest capacity, minimum nights and host listing count use `log1p` transformations. Residual smearing converts log predictions back to dollars.

Every recommendation uses the same reference setup: **two bedrooms, one bathroom, four guests, a two-night minimum, a non-Superhost and one host listing**. Training includes properties with different sizes; fixing the prediction setup makes locations more comparable. It does not establish that two bedrooms are optimal or justify extrapolation to unrealistic property sizes.

Exact suburb × format combinations need at least **10 listings and 8 hosts** to receive a separate revenue-model effect; others enter a pooled reference group. The final model covers **157 supported combinations**. A **Strong** evidence label additionally requires:

- at least 20 listings and 10 hosts;
- a positive lower confidence limit for the segment's log-revenue effect relative to the pooled reference;
- a Benjamini–Hochberg false-discovery-rate-adjusted q-value below 0.05.

Moderate evidence passes the statistical checks but not the stronger sample-size rules; remaining modelled combinations are exploratory. Revenue-only recommendations rank Strong options by the lower end of the model-based revenue interval, not simply the largest point estimate. A 95% confidence interval describes uncertainty in the estimated segment mean; it is not an individual property's earnings range or a guaranteed floor.

### 3.2 Model comparison and validation

Section 11 benchmarks log-linear regression, random forest and histogram gradient boosting **before** generating the retained regression's recommendations.

All three use the same target and inputs. An 80/20 host-grouped split reserves unseen hosts; three-fold host-grouped cross-validation within training data selects challenger settings using dollar mean absolute error (MAE). Missing-value replacements and combination-support rules are learned within each benchmark training fold, preventing held-out records from influencing those fitted preparation rules. Seed: `30005`.

| Model | Test MAE, AUD ↓ | Test RMSE, AUD ↓ | Test log-revenue R² ↑ |
|---|---:|---:|---:|
| Log-linear regression | 17,043 | **23,233** | **0.249** |
| Random forest | 16,989 | 23,557 | 0.239 |
| Histogram gradient boosting | **16,866** | 23,274 | 0.245 |

MAE measures average absolute error; root mean squared error (RMSE) gives larger errors more weight. The R² column is on the **log-revenue scale**, not dollars.

Boosting wins training-CV MAE and test MAE, improving test MAE by approximately **1.04%** relative to benchmark regression. Its host-bootstrap improvement interval includes zero, so this check does not establish a clear positive improvement; it does not prove equivalence either. Regression has the lowest test RMSE and highest test log R². We retain it for transparent adjusted comparisons and uncertainty estimates, not because it wins every metric.

The later recommendation regression preserves the original comprehensive specification and reports a separate test MAE of approximately **AUD 17,230**, RMSE of **AUD 23,584** and log R² of **0.244**. Its upstream preparation differs from the training-only benchmark. Do not merge these metric rows or claim that every analysis is completely free of full-sample preprocessing.

AIC is not used as a common score for these three model classes: an appropriate shared likelihood and complexity penalty have not been established. Cross-validation, unseen-host errors and bootstrap checks provide the model-comparison evidence.

Detailed scenario estimates remain in the notebook's technical appendix. Similar predictive errors do **not** imply identical suburb estimates: for example, Collingwood's estimated gross yield is approximately 4.37% under the retained recommendation regression, 3.23% under benchmark boosting and 1.92% under benchmark random forest. This is material model sensitivity.

### 3.3 Purchase-price proxies and gross yield

[property_price_merge.py](property_price_merge.py) prepares acquisition benchmarks separately from the revenue model.

1. Match the VGV **2025 median sale price** to the listing's suburb and broad **House or Unit** class.
2. Match DFFH bedroom-specific rent and letting counts to the appropriate rental market and class.
3. Calculate a typical rent anchor: the **letting-count-weighted median of bedroom-category median rents**.
4. Scale the VGV median by the bedroom-rent ratio.

```text
Purchase-price proxy
  = VGV suburb/class median sale price
  × (bedroom-specific median weekly rent ÷ typical weekly rent)

Estimated gross yield (%)
  = adjusted predicted annual revenue ÷ purchase-price proxy × 100
```

Typical rent is not a Melbourne-wide average or the pooled median of individual leases. Letting counts determine the weight of each bedroom category. Matching prefers exact or explicitly grouped markets and labelled aliases, with a recorded council-level market fallback where supported, including Yarra Ranges for Healesville. Unavailable or unsupported matches remain missing with a status flag.

The scaling assumes relative long-term rents approximate relative purchase prices across bedroom categories. It is **our modelling assumption, not a government valuation method**. At least two valid bedroom categories are required; published categories cover 1–3-bedroom flats and 2–4-bedroom houses. Houses and units use different sale and rental benchmarks, even with the same bedroom count. No fitted acquisition-price regression or log transformation is used.

The main analysis joins two-bedroom acquisition proxies to the common revenue scenario; **125 of 157** supported combinations have valid acquisition coverage. Reported yield intervals hold the price proxy fixed and do not include purchase-price uncertainty. Separate Airbnb nightly-price peer comparisons are not inputs to the purchase-price calculation.

### 3.4 Seasonal complement

Reviews measure guest activity, not bookings or monthly revenue. Established-listing cohorts are followed across **June 2023–May 2026**, with review events divided by cohort listing count and calendar days and displayed per 30 days.

- **Selection window:** June 2023–May 2025 identifies Collingwood's weakest season, winter.
- **Candidate eligibility:** Strong revenue evidence, a valid acquisition proxy, at least 30 established listings, 15 hosts, median monthly review volume of at least 20, and higher review activity during Collingwood's weaker season.
- **Selection rule:** choose the eligible complement with the highest estimated gross yield.
- **Following-year check:** June 2025–May 2026 examines whether the winter advantage persists and whether an equal-normalised activity pair is less variable.

Matched charts use the same periods, seasons, units and vertical scales for both locations. Collingwood's cohort contains 43 listings from 38 hosts; Healesville's contains 50 listings from 41 hosts.

This is descriptive seasonal analysis, not a fitted forecasting model. Review-volume eligibility uses the full 36 months and revenue/acquisition inputs use the current snapshot, so the following-year check is not a completely untouched investment backtest. It is separate from unseen-host revenue-model validation.

### 3.5 Operating choices and guest experience

- **Amenities:** controlled log-revenue models compare supplied revenue and the reconstructed review proxy, with host-clustered inference and multiple-testing adjustment. Positive associations do not establish an installation return or account for installation costs.
- **Minimum stays:** controlled nonlinear models compare review activity and supplied estimated revenue across stay-policy scenarios. They are observational comparisons, not experiments.
- **Guest ratings:** reliability-adjusted component scores predict **overall guest rating**, not revenue. Controls-only, linear-score and nonlinear-score models are compared across ten host-grouped splits. Conditional importance measures the loss of test prediction performance when one score is removed. Rare-suburb pooling below 20 listings belongs to this rating model; it is not the separate revenue-combination threshold. Column-scaled, truncated-SVD least squares stabilises the numerical calculations. Correlated categories can share information, so importance is neither a causal effect nor Airbnb's algorithm weight.

## 4. Findings and client recommendations

All amounts below are AUD. These are common two-bedroom reference scenarios, not suburb-wide raw averages.

| Segment | Estimated annual gross revenue | Purchase-price proxy | Estimated gross yield | Decision role |
|---|---:|---:|---:|---|
| Collingwood — whole apartment/unit | 27,533 | 630,000 | **4.37%** | First priority for acquisition due diligence among Strong-evidence options |
| Healesville — whole house | 26,299 | 678,992 | **3.87%** | Second-location candidate for seasonal demand balance |
| Fitzroy — whole apartment/unit | 26,100 | 805,000 | **3.24%** | Highest conservative revenue-only ranking among Strong-evidence options |

Fitzroy's model-based mean-revenue interval is approximately **AUD 21,544–31,619**, supported by 113 listings from 82 hosts. Collingwood has a higher revenue point estimate but a slightly lower interval endpoint; accounting for acquisition cost changes the preferred investment shortlist.

Healesville's winter review activity exceeds Collingwood's by **26.2%** in the selection period and **50.3%** in the following year. Its own peak is spring in the selection period and autumn in the following year; winter is **not** its busiest season in either period. Regional visitor research provides context for winter attractions, not proof that a particular attraction caused Airbnb stays.

For operations:

- A one-night minimum is associated with approximately **37% more reviews and 28% higher estimated revenue** than a two-night minimum in the controlled scenarios. Trial shorter stays against cleaning costs, turnover workload, dynamic date-specific rules and net income.
- Smart entry, stainless-steel ovens and views are the leading positive cross-checked amenity associations in the current analysis. Treat them as priorities for feasibility and cost testing, not guaranteed gains or a universal shopping list.
- Accuracy is the strongest conditional predictor of overall guest rating, followed by cleanliness and value. Maintain truthful descriptions and reliable delivery; the model does not prove that improving a score will raise bookings or revenue.

## 5. Limitations and future work

- Supplied revenue and reconstructed occupancy are estimates based on assumptions, not verified transactions. Quoted prices need not equal realised booking prices.
- Reviews are an imperfect demand proxy; review propensity, season-specific booking values and exact occupied nights are unavailable. Unavailable calendar dates may be booked or host-blocked.
- Airbnb's anonymised coordinates may cross suburb boundaries, particularly near small localities. Boundary-buffer sensitivity checks and verified addresses would improve geographic confidence.
- Host-reported property formats are broad categories, not verified legal or valuation classifications.
- Acquisition proxies omit condition, land/floor area, bathrooms, parking, exact address and property-specific sales evidence. Council-level rental fallbacks reduce local precision.
- Gross yields exclude transaction costs, financing, cleaning, maintenance, management, utilities, strata/body-corporate charges, levies and tax. They are neither net cash flow nor ROI.
- Predictive performance is moderate, recommendations are sensitive to model specification, and observational associations do not establish causation.
- One following-year seasonal cycle cannot establish future performance across changing tourism or economic conditions. The activity pair is not a simulated portfolio of actual cash receipts.

Next steps are property-level comparable-sales checks, permission and cost due diligence, validated booking/revenue data, more seasonal cycles, and controlled operating trials. Model complexity should increase only if repeatable predictive improvements justify reduced interpretability.

## 6. Repository guide

| Path | Purpose |
|---|---|
| [Group6_analysis_final.ipynb](Group6_analysis_final.ipynb) | **Main final workflow:** cleaning, model comparison, retained regression, acquisition cross-check, amenities, ratings, minimum stays and seasonality |
| [property_price_merge.py](property_price_merge.py) | Reusable purchase-price preparation functions and command-line entry point |
| [Testing/test_property_price_merge.py](Testing/test_property_price_merge.py) | Synthetic-data tests for rent weighting, matching, formula logic and export provenance |
| `listings_with_property_price_benchmarks.csv` | Required generated input; retain its source-reference and matching-status columns |
| [Group6_cleaning_suburb_regression_merged.ipynb](Group6_cleaning_suburb_regression_merged.ipynb) | Upstream cleaning notebook exporting `listings_clean_merged_with_suburb.csv` for a raw-to-proxy rebuild |
| [Testing/property_price_merge.ipynb](Testing/property_price_merge.ipynb) | Companion preparation notebook; the Python file remains the reusable implementation |
| `Testing/comprehensive_analysis/` | Derived recommendation tables, coverage audits and figures |
| `Testing/comprehensive_analysis/revenue_model_comparison/` | Benchmark metrics, tuning, split audit, bootstrap checks, scenario sensitivity and run metadata |
| `Testing/seasonal_complement/` | Matched seasonal figures and comparable review-rate table |
| [Testing/Group6_comprehensive_analysis.ipynb](Testing/Group6_comprehensive_analysis.ipynb) | Earlier comprehensive version; not the final model-comparison workflow |
| [Testing/Group6_revenue_model_comparison.ipynb](Testing/Group6_revenue_model_comparison.ipynb) | Earlier standalone benchmark; the final notebook integrates the comparison |
| Other exploratory notebooks and older notes | Development history; not the source of final recommendations |

**Output-version warning:** existing `Testing/comprehensive_analysis/review_score_*.csv` exports include results from an earlier, numerically unstable run. Do not use those stale values for final reporting. The stabilised results are stored in the final notebook; run that notebook through its export cell to regenerate consistent CSVs. Earlier property-merge notes also describe an older matching version; use the current Python file and its output provenance for the implemented method.

## 7. Reproducing the analysis

### Environment

Use Python 3.10 or later with Jupyter. The recorded model benchmark used Python **3.13.9** and scikit-learn **1.7.2**; its `run_metadata.json` records the seed, parameters, input hashes and split sizes.

From a terminal in the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install jupyterlab ipykernel pandas numpy matplotlib scipy statsmodels patsy scikit-learn==1.7.2 geopandas shapely openpyxl
.\.venv\Scripts\python.exe -m jupyter lab
```

These commands use the virtual environment directly and do not require changing PowerShell's activation policy. They are setup instructions, not a fully pinned lockfile; package or input changes can affect reproduction.

### A. Run the final analysis using the supplied benchmark CSV

1. Place `listings_airbnb.csv`, `reviews_airbnb.csv`, `calendar_airbnb.csv` and `listings_with_property_price_benchmarks.csv` together in the project root. Raw data is not bundled automatically.
2. Keep `vic_suburbs.geojson` in the root. If absent, the notebook attempts to download its documented GitHub source; download it manually if network access is blocked.
3. Open **`Group6_analysis_final.ipynb`**, restart its kernel and run all cells sequentially using the prepared environment.
4. Check the input integrity assertions, host-disjoint splits, evidence tiers and acquisition-coverage diagnostics.
5. Run the final export cell and technical appendix. Outputs are written automatically; there is no `EXPORT_CURRENT_RESULTS` switch in this final workflow. Existing named outputs are replaced, not raw source data.
6. Use tables and figures from the same completed run. Check the matched seasonal charts and the benchmark metadata before copying results into the report.

The main benchmark and seasonal functions are defined inside the final notebook; no separate portfolio module or RBA workbook download is required.

### B. Rebuild the purchase-price input from its sources

This is a separate preparation stage. The main notebook requires the generated benchmark CSV at setup, so it cannot bootstrap this input from nothing.

1. Obtain the raw Airbnb files and locality boundaries.
2. Use the upstream cleaning notebook to produce `listings_clean_merged_with_suburb.csv`. Its export cell also writes earlier amenity tables, so back up any same-named outputs before rerunning that development notebook.
3. Place the three official VGV/DFFH workbooks named in Section 2 inside `Testing/`. The preparation script does not download them.
4. From the project root, run:

```powershell
.\.venv\Scripts\python.exe property_price_merge.py listings_clean_merged_with_suburb.csv Testing/VGV_houses_by_suburb_2015-2025.xlsx Testing/VGV_units_by_suburb_2015-2025.xlsx . --dffh-workbook Testing/DFFH_moving_annual_rent_by_suburb_September_2025.xlsx --audit-directory Testing
```

This replaces the root benchmark CSV and named audit outputs in `Testing/`. For a trial run, supply a different output directory. Source-reference columns, source periods, workbook filenames, mapping methods and adjustment-status flags travel with the CSV.

Run the preparation tests with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s Testing -p test_property_price_merge.py -v
```

Then follow workflow A to regenerate the analytical results. Rebuilding the CSV changes its file hash; compare data values and recorded source versions, not just an older metadata hash.

### Submission checklist

The submission must include **both**:

- project-root `property_price_merge.py`;
- project-root `listings_with_property_price_benchmarks.csv`.

Include the final notebook and this README as well. The companion preparation notebook does not replace the Python script or CSV.

The current `.gitignore` excludes `*.csv` and `*.xlsx`, so local existence does not mean a file is committed or uploaded. Stage the required generated CSV explicitly:

```powershell
git add README.md Group6_analysis_final.ipynb property_price_merge.py Testing/test_property_price_merge.py
git add -f -- listings_with_property_price_benchmarks.csv
git diff --cached --stat
```

Review the staged files before committing. Do not force-add all raw files or remove blanket ignore rules just to include one required output. Document access to any excluded source files and verify the required files on GitHub after pushing.

## 8. Contribution record

Entries before 18 September 2026 were **retrospectively reconstructed from group work and message history; they are not claimed to be Git commits**. Individual attribution should be verified by the team.

| Date | Member / record | Work completed | File / section |
|---|---|---|---|
| Before 18 Sep 2026 — retrospective | Group 6 | Data cleaning, review windows, stay-policy variables, suburb allocation and price/amenity modelling | Earlier notebooks; comprehensive workflow Sections 1–10 |
| 18 Sep 2026 | Group 6 | Replaced hard-coded recommendation multipliers with supported combinations, uncertainty checks and host-grouped validation; documented refined scope | Comprehensive workflow Sections 11–13; interim README |
| 23 Oct 2026 — documentation update | README revision | Replaced interim status with final findings, model trade-offs, acquisition provenance, seasonal limitations and final-workflow instructions | `README.md` |

## 9. References and data access

Data coverage dates are stated separately from publication dates. The notebook, preparation script and exported provenance columns provide the operational source details.

- Benjamini, Y., & Hochberg, Y. (1995). Controlling the false discovery rate: A practical and powerful approach to multiple testing. *Journal of the Royal Statistical Society: Series B, 57*(1), 289–300. [https://doi.org/10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)
- Department of Families, Fairness and Housing. (2026). *Rental report* [Datasets; September 2025 moving-annual workbook used]. [Source page](https://www.dffh.vic.gov.au/publications/rental-report)
- Duan, N. (1983). Smearing estimate: A nonparametric retransformation method. *Journal of the American Statistical Association, 78*(383), 605–610. [https://doi.org/10.1080/01621459.1983.10478017](https://doi.org/10.1080/01621459.1983.10478017)
- Inside Airbnb. (n.d.). *Data assumptions*. [Methodology](https://insideairbnb.com/data-assumptions/)
- Inside Airbnb. (2026). *Melbourne listings, reviews and calendar: June 2026* [Datasets]. [Data access](https://insideairbnb.com/get-the-data/)
- Valuer-General Victoria. (2026). *Property sales statistics* [Datasets; 2025 house and unit medians used]. [Source page](https://www.land.vic.gov.au/valuations/resources-and-reports/property-sales-statistics)
- Wright, A. (2017). *suburb-2-vic.geojson* [Data set]. GitHub. [Boundary file](https://github.com/anthwri/GeoJson-Data/blob/master/suburb-2-vic.geojson). See also the [DataVic locality dataset description](https://discover.data.vic.gov.au/dataset/vicmap-admin-locality-polygon-aligned-to-property).

For current operating requirements, consult [Consumer Affairs Victoria](https://www.consumer.vic.gov.au/housing/owners-corporations/rules/making-rules-to-ban-short-stay-accommodation) and the [Victorian State Revenue Office](https://sro.vic.gov.au/owning-property/short-stay-levy/understanding-short-stay-levy). These checks are part of property due diligence, not costs modelled in this analysis.

*Last updated: 23 October 2026.*
