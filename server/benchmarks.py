def get_benchmark_options(results):
    for each in results["CV_COMMON_TICKER_EXCH"]:
        for ticker, price, maturity in results[["CV_COMMON_TICKER_EXCH", "CV_CNVS_PX", "MATURITY"]].itertuples(index=False, name=None):
            query = f"""
let(
    #delta_maturity = abs(expire_dt() - {maturity})
)
get(   
    name(),
    strike_px(),
    expire_dt(),
    put_call(),
    #expiry_delta
)
for(
    top(
        filter(
            options({ticker}),
            put_call() == 'Call'
            and strike_px() >= {price*0.95}
            and strike_px() <= {price*1.05}
        ),
        1,
        -#expiry_delta
    )
)

"""
    # Placeholder implementation - replace with actual benchmark option logic
    return results  # Return the results as-is for now
