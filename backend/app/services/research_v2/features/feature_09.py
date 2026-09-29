"""F09 Synthetic Control Engine."""

from __future__ import annotations

from typing import Any

from ..core.common import response
from ..core.synthetic import VARIANTS, run_synthetic
from .inputs import field, output

FEATURE_ID = "09"
FEATURE_NAME = "Synthetic Control Engine"
DESCRIPTION = "Counterfactual for a single treated asset from a weighted donor pool: classic, augmented, generalized and robust SCM with placebo, leave-one-out and conformal inference."

INPUTS = [
    field("treated_unit", "Treated unit", "ticker", "", "Treatment", help_="A ticker, sector ETF or country ETF."),
    field("treatment_date", "Treatment date", "date", None, "Treatment"),
    field("event_csv_path", "Event file (staggered mode)", "file", "", "Treatment"),
    field("multiple_treated", "Multiple treated units", "select", "off", "Treatment", ["off", "staggered"]),
    field("donor_pool", "Donor pool", "select", "all_untreated", "Donors", ["all_untreated", "user_list", "same_sector", "same_size_decile"]),
    field("donor_list", "Donor tickers", "ticker_list", "", "Donors"),
    field("universe", "Donor universe", "ticker_list", "us_equities", "Donors"),
    field("max_symbols", "Donor candidates", "number", 200, "Donors", min=20, max=1000),
    field("donor_limit", "Max donors", "number", 60, "Donors", min=10, max=200),
    field("scm_variant", "SCM variant", "select", "classic", "Method", sorted(VARIANTS)),
    field("conformal_alpha", "Conformal alpha", "select", 0.1, "Method", [0.05, 0.1]),
    field("lookback_days", "Lookback (days)", "number", 3650, "Method", min=1460, max=11000),
]

OUTPUTS = [
    output("treatment_effect", "Treatment effect", "tables", "keyValue", primary=True),
    output("treated_vs_synthetic_path", "Treated vs synthetic", "charts", "syntheticPath"),
    output("gap_plot", "Gap", "charts", "gapPlot"),
    output("placebo_gap_paths", "Placebo gaps", "charts", "placeboPaths"),
    output("rmspe_ratio_chart", "Post/pre RMSPE ratios", "charts", "placeboRanking"),
    output("rmspe_ratio_ranking", "Placebo inference", "tables", "testCard"),
    output("pre_treatment_fit", "Pre-treatment fit", "tables", "testCard"),
    output("donor_weight_table", "Donor weights", "tables", "dataTable"),
    output("donor_concentration", "Donor concentration", "tables", "keyValue"),
    output("leave_one_out_sensitivity", "Leave-one-out", "tables", "dataTable"),
    output("leave_one_out_summary", "Leave-one-out range", "tables", "keyValue"),
    output("in_time_placebo", "In-time placebo", "tables", "keyValue"),
    output("conformal_band", "Conformal band", "charts", "conformalBand"),
    output("staggered_event_study", "Staggered adoption", "charts", "eventStudy"),
    output("staggered_adoption_scm", "Staggered units", "tables", "dataTable"),
    output("variant_details", "Method details", "tables", "keyValue"),
    output("latex_export", "LaTeX", "tables", "latex"),
]


def run(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    out = run_synthetic(payload or {})
    return response(FEATURE_ID, out["summary"], out["charts"], out["tables"], out["meta"])
