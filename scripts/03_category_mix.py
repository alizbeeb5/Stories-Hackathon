"""Person 2 - Baskets & product mix: what customers buy - category share of units and revenue, and category margin, by branch."""
import pandas as pd
pd.set_option("display.width", 200)
import sys, os
# Usage: python <script>.py [path/to/stories_transactions.csv]
# Default: looks for data/stories_transactions.csv in the repo (or next to the script).
HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [os.path.join(HERE, "data", "stories_transactions.csv"), os.path.join(HERE, "..", "data", "stories_transactions.csv"),
              os.path.join(HERE, "stories_transactions.csv")]
DATA = sys.argv[1] if len(sys.argv) > 1 else next((p for p in CANDIDATES if os.path.exists(p)), CANDIDATES[0])
os.makedirs("out", exist_ok=True)
df = pd.read_csv(DATA)
R, G = "Line Revenue (USD)", "Line Gross Profit (USD)"
units = pd.crosstab(df.Category, df.Branch, values=df.Quantity, aggfunc="sum", normalize="columns") * 100
rev = pd.crosstab(df.Category, df.Branch, values=df[R], aggfunc="sum", normalize="columns") * 100
margin = (df.groupby(["Category", "Branch"])[G].sum() / df.groupby(["Category", "Branch"])[R].sum() * 100).unstack()
baskets_with = df.groupby(["Branch", "Category"])["Transaction ID"].nunique().unstack(0) / df.groupby("Branch")["Transaction ID"].nunique() * 100
out = pd.concat({"units_%": units, "revenue_%": rev, "baskets_containing_%": baskets_with, "margin_%": margin}, axis=1).round(1)
out = out.sort_values(("margin_%", "Harbour"))
out.to_csv("out/03_category_mix.csv")
print(out.to_string())
