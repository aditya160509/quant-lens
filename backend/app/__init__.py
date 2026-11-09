import os

os.environ.setdefault('POLARS_MAX_THREADS', '2')  # read once at Polars import; measured to halve Screener peak memory
