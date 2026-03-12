import pandas as pd
import json
import os

# 1. Define the filename
filename = 'sme_statutes_db.json'

print(f"Loading data from {filename}...\n")

try:
    # 2. Load the JSON data
    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 3. Convert to a Pandas DataFrame
    df = pd.DataFrame(data)

    print("=========================================")
    print("      LEGAL DATA ANALYSIS REPORT         ")
    print("=========================================\n")

    # --- CORE METRICS ---

    # A. Total number of unique acts
    total_unique_acts = df['act'].nunique()
    print(f"1. Total Unique Acts: {total_unique_acts}")

    # B. Number of sections per act
    sections_per_act = df.groupby('act')['section'].nunique()
    print("\n2. Number of Unique Sections Per Act:")
    print("-" * 37)
    print(sections_per_act.to_string())
    print("-" * 37)

    # C. Average word length of full text
    df['word_count'] = df['full_text'].fillna("").astype(str).apply(lambda x: len(x.split()))
    avg_word_count_overall = df['word_count'].mean()
    print(f"\n3. Overall Average Word Count per entry: {avg_word_count_overall:.2f} words")

    # Average word length per individual act
    avg_word_count_per_act = df.groupby('act')['word_count'].mean()
    print("\n4. Average Word Count Per Act:")
    print("-" * 37)
    print(avg_word_count_per_act.round(2).to_string())
    print("-" * 37)

    # --- OTHER FACTORS / INSIGHTS ---
    print("\n--- Additional Insights ---")

    # D. Total number of data entries scraped
    print(f"* Total Data Entries (Rows) Scraped: {len(df)}")

    # E. Keyword Analysis
    df['keyword_count'] = df['keywords'].apply(lambda x: len(x) if isinstance(x, list) else 0)
    avg_keywords = df['keyword_count'].mean()
    print(f"* Average Keywords per Section: {avg_keywords:.2f}")

    if 'keywords' in df.columns:
        all_keywords = df['keywords'].explode().dropna()
        if not all_keywords.empty:
            most_common_keyword = all_keywords.value_counts().head(1)
            print(f"* Most Common Keyword: '{most_common_keyword.index[0]}' (Appears {most_common_keyword.values[0]} times)")

    # F. Unique PDF URLs
    if 'pdf_url' in df.columns:
        unique_pdfs = df['pdf_url'].nunique()
        print(f"* Total Unique PDF Documents Linked: {unique_pdfs}")

except FileNotFoundError:
    print(f"Error: Could not find '{filename}'.")
    print(f"Please ensure '{filename}' is located inside: {os.getcwd()}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")