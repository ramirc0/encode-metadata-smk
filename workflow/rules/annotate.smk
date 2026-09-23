# Annotation / experiment / file parquets -> per-model tables + aria2c manifests.


rule model_annotations:
    input:
        annotation=annotation_input("annotation"),
        experiment=annotation_input("experiment"),
        file=annotation_input("file"),
    output:
        table=f"{OUTDIR}/annotations/{{model}}-model-annotations.parquet",
        tsv=f"{OUTDIR}/annotations/{{model}}-model-annotations.tsv",
        manifest=f"{OUTDIR}/annotations/{{model}}-model-annotations.manifest",
    params:
        flags=lambda w: model_flags(w.model),
    log:
        f"{LOGDIR}/model_annotations/{{model}}.txt",
    benchmark:
        f"{BENCHDIR}/model_annotations/{{model}}.tsv",
    conda:
        CONDA_ENV
    shell:
        r"""
        exec &> >(tee {log:q})

        python workflow/scripts/model_annotations.py \
            --annotation {input.annotation:q} \
            --experiment {input.experiment:q} \
            --file {input.file:q} \
            --model {wildcards.model:q} \
            --out-table {output.table:q} \
            --out-tsv {output.tsv:q} \
            --out-manifest {output.manifest:q} \
            {params.flags:q}
        """
