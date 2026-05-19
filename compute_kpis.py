import pandas as pd

def compute_kpis():
    df = pd.read_csv("evaluation_results.csv")

    total = len(df)

    # 1. Intent Accuracy
    intent_accuracy = df["intent_correct"].sum() / total

    # 2. Relevance Score
    relevance = df["relevance_score_1_5"].mean()

    # 3. Clarity Score
    clarity = df["clarity_score_1_5"].mean()

    # 4. Language Quality
    language_ok = (df["language_ok_yes_no"] == "yes").sum() / total

    # 5. Hallucination Rate
    hallucination_rate = (df["hallucination_yes_no"] == "yes").sum() / total

    # 6. Product Accuracy (ignore NA)
    product_df = df[df["product_accuracy_yes_no_na"].isin(["yes", "no"])]

    if len(product_df) > 0:
        product_accuracy = (product_df["product_accuracy_yes_no_na"] == "yes").sum() / len(product_df)
    else:
        product_accuracy = None

    # 7. Response Time
    response_time = df["response_time_sec"].mean()

    print("\n📊 ===== CHATBOT KPI RESULTS =====\n")

    print(f"🧠 Intent Accuracy: {intent_accuracy:.2%}")
    print(f"🎯 Relevance Score: {relevance:.2f} / 5")
    print(f"💬 Clarity Score: {clarity:.2f} / 5")
    print(f"🌍 Language Quality: {language_ok:.2%}")
    print(f"⚠️ Hallucination Rate: {hallucination_rate:.2%}")

    if product_accuracy is not None:
        print(f"📦 Product Accuracy: {product_accuracy:.2%}")
    else:
        print("📦 Product Accuracy: N/A")

    print(f"⚡ Avg Response Time: {response_time:.2f} sec")

    print("\n=================================\n")


if __name__ == "__main__":
    compute_kpis()