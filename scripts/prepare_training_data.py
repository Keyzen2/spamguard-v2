import pandas as pd
import json

def load_and_prepare():
    """Cargar todos los datasets y combinar"""
    
    # Cargar SpamAssassin
    spam = load_spamassassin('data/raw/spam')
    ham = load_spamassassin('data/raw/ham')
    
    # Combinar
    df = pd.concat([spam, ham])
    
    # Shuffle
    df = df.sample(frac=1).reset_index(drop=True)
    
    # Split
    train_size = int(0.8 * len(df))
    val_size = int(0.1 * len(df))
    
    train = df[:train_size]
    val = df[train_size:train_size+val_size]
    test = df[train_size+val_size:]
    
    # Guardar
    train.to_json('data/train.jsonl', orient='records', lines=True)
    val.to_json('data/val.jsonl', orient='records', lines=True)
    test.to_json('data/test.jsonl', orient='records', lines=True)
    
    print(f"✓ Train: {len(train)}")
    print(f"✓ Val: {len(val)}")
    print(f"✓ Test: {len(test)}")

if __name__ == '__main__':
    load_and_prepare()
