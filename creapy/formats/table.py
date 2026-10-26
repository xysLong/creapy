import csv
import os
import pandas as pd

# EyeLink DataViewer writes a '.' for missing values; Tobii Pro Lab leaves cells empty
MISSING_VALUES = ['.', '', 'NA', 'NaN', 'nan', 'None']

TEXT_EXTENSIONS = ['.csv', '.tsv', '.txt', '.dat']
EXCEL_EXTENSIONS = ['.xlsx', '.xlsm', '.xls']


def sniff_delimiter(path, encoding):
    """
    Guess the column separator of a text table from its header line: tab, ';', ',' or '|', whichever occurs
    most often (csv.Sniffer only when none of them appears, ',' if even that fails). The counting is there
    because German Excel exports with ';' and decimal commas fool csv.Sniffer.
    """
    # csv.Sniffer gets German Excel exports (';' with decimal commas) wrong often enough
    # that counting the candidates on the header line is the more reliable guess.
    with open(path, 'r', encoding=encoding, errors='replace') as f:
        header = f.readline()
    counts = {sep: header.count(sep) for sep in ['\t', ';', ',', '|']}
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        try:
            return csv.Sniffer().sniff(header).delimiter
        except csv.Error:
            return ','
    return best


def read_table(path, sheet_name=0):
    """
    Read one table (CSV/TSV/TXT with any common delimiter, or Excel with `sheet_name`) into a DataFrame.
    utf-8 first, latin-1 as fallback; '.', empty cells, 'NA', 'NaN' and 'None' become NaN (EyeLink DataViewer
    writes '.' for missing values); decimal commas are converted, numeric-looking text columns are coerced
    to numbers, column names are stripped and all-empty columns dropped.
    """
    # One table in, one DataFrame out: CSV/TSV/TXT with any common delimiter (incl. the ';' + decimal-comma
    # dialect of German Excel), or Excel. Numeric-looking text columns are converted; EyeLink's '.' becomes NaN.
    ext = os.path.splitext(path)[1].lower()
    if ext in EXCEL_EXTENSIONS:
        df = pd.read_excel(path, sheet_name=sheet_name, na_values=MISSING_VALUES, keep_default_na=True)
    elif ext in TEXT_EXTENSIONS or ext == '':
        encoding = 'utf-8-sig'
        try:
            sep = sniff_delimiter(path, encoding)
        except UnicodeDecodeError:
            encoding = 'latin-1'
            sep = sniff_delimiter(path, encoding)
        df = pd.read_csv(path, sep=sep, encoding=encoding, na_values=MISSING_VALUES, keep_default_na=True,
                         low_memory=False)
        # German-locale exports (Excel ';' files, but also Tobii TSVs) write 12,5: convert wherever a column
        # becomes numeric by the swap; the 95 % guard keeps genuine text columns untouched
        df = convert_decimal_commas(df)
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Please use .csv, .tsv, .txt or .xlsx.")
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=1, how='all')
    return coerce_numeric(df)


def convert_decimal_commas(df):
    """
    Turn '12,5' into 12.5 in text columns where at least 95 % of the non-empty values become numbers after
    the swap; other columns stay as they are. Modifies df in place and returns it.
    """
    # '12,5' -> 12.5 in object columns where (almost) everything parses after the swap
    for col in df.columns:
        if df[col].dtype == object:
            swapped = pd.to_numeric(df[col].astype(str).str.replace(',', '.', regex=False), errors='coerce')
            if swapped.notna().sum() >= 0.95 * df[col].notna().sum() > 0:
                df[col] = swapped
    return df


def coerce_numeric(df):
    """
    Make text columns numeric where at least 95 % of the non-empty values parse as numbers; the rest
    (e.g. EyeLink's '.') become NaN. Modifies df in place and returns it.
    """
    # Object columns that are numbers in disguise (mixed in with the '.' placeholders) become floats
    for col in df.columns:
        if df[col].dtype == object:
            as_num = pd.to_numeric(df[col], errors='coerce')
            if as_num.notna().sum() >= 0.95 * df[col].notna().sum() > 0:
                df[col] = as_num
    return df


def numeric_columns(df):
    """
    Names of the columns with a numeric dtype.
    """
    return [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]


def image_like_columns(df):
    """
    Names of the text columns whose values (the first 200 non-empty ones) mostly end in an image extension
    (png, jpg, bmp, tif, gif, webp) - candidates for the stimulus column.
    """
    # Columns whose values look like image file names or paths: candidates for the stimulus column
    ls = []
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().astype(str).head(200).str.lower()
            if len(sample) and sample.str.contains(r'\.(?:png|jpe?g|bmp|tiff?|gif|webp)$', regex=True).mean() > 0.8:
                ls.append(col)
    return ls


if __name__ == '__main__':
    pass
