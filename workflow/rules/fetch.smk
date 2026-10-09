# ENCODE report.tsv -> cleaned TSV -> Parquet, one report per job.


# Output name comes from the committed sheet, not ENCODE's Content-Disposition
# header, so no date suffix has to be parsed back off.
rule fetch_report:
    output:
        f"{OUTDIR}/reports/{{report}}.raw.tsv",
    params:
        url=lambda w: URL_OF[w.report],
        netrc=NETRC_FLAGS,
    log:
        f"{LOGDIR}/fetch_report/{{report}}.txt",
    benchmark:
        f"{BENCHDIR}/fetch_report/{{report}}.tsv",
    resources:
        encode_api=1,
    software:
        SOFTWARE_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        aria2c {params.url:q} \
            --dir {OUTDIR:q}/reports \
            --out {wildcards.report:q}.raw.tsv \
            {params.netrc:q} \
            --continue=true \
            --max-connection-per-server=4 \
            --split=4 \
            --min-split-size=1M \
            --auto-file-renaming=false \
            --allow-overwrite=true
        """


# ENCODE prefixes every report with a one-line metadata banner above the header.
rule clean_report:
    input:
        f"{OUTDIR}/reports/{{report}}.raw.tsv",
    output:
        f"{OUTDIR}/reports/{{report}}.tsv",
    log:
        f"{LOGDIR}/clean_report/{{report}}.txt",
    benchmark:
        f"{BENCHDIR}/clean_report/{{report}}.tsv",
    software:
        SOFTWARE_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        tail -n +2 {input:q} \
            | qsv fmt \
                --delimiter '\t' \
                --out-delimiter '\t' \
            > {output:q}
        """


rule report_parquet:
    input:
        f"{OUTDIR}/reports/{{report}}.tsv",
    output:
        f"{OUTDIR}/parquets/{{report}}.parquet",
    log:
        f"{LOGDIR}/report_parquet/{{report}}.txt",
    benchmark:
        f"{BENCHDIR}/report_parquet/{{report}}.tsv",
    software:
        SOFTWARE_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        python workflow/scripts/report_to_parquet.py \
            --input {input:q} \
            --output {output:q}
        """
