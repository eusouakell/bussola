# Estado vivo de um serviço Cloud Run como values do modo promoção do chart
# (templates/promotion.yaml). Entrada: `gcloud run services describe --format=json`.
#
#   jq --arg key agent --arg target main -f deploy/helm/promote.jq service.json
#
# $target: main, cNNN, previous (rollback) ou nome de revisão. O chart valida
# o alvo e o tráfego; este filtro só copia o estado vivo, sem decidir nada.
# O spec.template vai inteiro, para o replace não criar revisão.
(.metadata.annotations // {}) as $annotations
| {
    promotion: {
      service: $key,
      target: $target,
      live: {
        name: .metadata.name,
        public: ($annotations["run.googleapis.com/invoker-iam-disabled"] == "true"),
        ingress: ($annotations["run.googleapis.com/ingress"] // "all"),
        template: .spec.template,
        traffic: [
          (.status.traffic // [])[]
          | {revisionName, percent: (.percent // 0)}
            + (if .tag then {tag} else {} end)
        ]
      }
    }
  }
