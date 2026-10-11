import pandas as pd

df = pd.read_csv("results/raw_results.csv")
core = df[(df["comm_regime"] == "nominal") & (df["adversary"].isin(["theta_1_stochastic", "theta_2_reactive", "theta_4_cyclic_patrol"]))]
print("Core grid method value counts:")
print(core["method"].value_counts())
print("\nTotal core rows:", len(core))
