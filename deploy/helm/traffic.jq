# Tráfego vivo de um serviço Cloud Run como values do chart
# (`services.<key>.traffic`). Entrada: `gcloud run services describe --format=json`.
#
#   jq --arg key agent --arg tag main -f deploy/helm/traffic.jq service.json
#
# Mantém revisões, percentuais e tags como estão: o deploy não move tráfego.
# A tag da revisão nova ($tag) é liberada de onde estiver com 0%. A tag `main`,
# que acompanha a última revisão da main, também sai de uma revisão que recebe
# tráfego; a revisão e o percentual ficam. Uma tag cNNN que recebe tráfego
# continua lá, e o chart recusa reutilizá-la.
{
  services: {
    ($key): {
      traffic: [
        (.status.traffic // [])[]
        | {revisionName, percent: (.percent // 0), tag}
        | if .tag == $tag then
            if .percent == 0 then empty
            elif $tag == "main" then .tag = null
            else . end
          else . end
        | select(.percent > 0 or .tag != null)
        | if .tag == null then del(.tag) else . end
      ]
    }
  }
}
