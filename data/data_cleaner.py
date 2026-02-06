def clean(df):
    df = df.dropna()
    df = df[df["volume"] > 0]
    return df