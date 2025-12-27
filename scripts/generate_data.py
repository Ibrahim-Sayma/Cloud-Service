import pandas as pd
import numpy as np
import argparse
import os

def generate_data(rows, output_file):
    print(f"Generating {rows} rows of data...")
    
    # Generate random data
    df = pd.DataFrame({
        'id': range(rows),
        'category': np.random.choice(['A', 'B', 'C', 'D'], rows),
        'value1': np.random.randn(rows),
        'value2': np.random.rand(rows) * 100,
        'value3': np.random.randint(0, 1000, rows)
    })
    
    # Introduce some nulls
    df.loc[df.sample(frac=0.05).index, 'value1'] = np.nan
    
    output_path = f"../storage/{output_file}"
    df.to_csv(output_path, index=False)
    print(f"Data saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--file", default="benchmark_data.csv")
    args = parser.parse_args()
    
    if not os.path.exists("../storage"):
        os.makedirs("../storage")
        
    generate_data(args.rows, args.file)
