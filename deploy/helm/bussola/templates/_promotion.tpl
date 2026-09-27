{{/*
Manifesto de promoção (ciclo 007): muda só o tráfego de um serviço.

Entrada (deploy/helm/promote.jq sobre o `gcloud run services describe`):
- promotion.service: chave do serviço (mcp, agent ou bff);
- promotion.target: tag (main, cNNN, previous) ou nome de revisão presente
  no tráfego vivo;
- promotion.live: nome, spec.template, tráfego, public e ingress vivos.

O spec.template vai sem mudança (mesmo nome de revisão): o
`gcloud run services replace` não cria revisão. O tráfego sai assim: 100% no
alvo, as tags vivas com 0% e a tag `previous` na revisão que servia. Rollback
= promover `previous`.

Falha antes do GCP quando: o serviço é desconhecido; o estado vivo é de
outro serviço; public ou ingress vivos diferem dos values (promover não muda
IAM nem ingress); o tráfego está dividido; o alvo não está no tráfego vivo ou
já recebe 100%. Mover tráfego exige confirmação humana (environment
production no promote.yml, docs/operacao.md).
*/}}
{{- define "bussola.promotion" -}}
{{- $root := .root -}}
{{- $key := toString .key -}}
{{- $promotion := $root.Values.promotion -}}
{{- if not (hasKey $root.Values.services $key) -}}
{{- fail (printf "promotion.service deve ser %s, veio %q" (keys $root.Values.services | sortAlpha | join ", ") $key) -}}
{{- end -}}
{{- $svc := index $root.Values.services $key -}}
{{- $live := $promotion.live | default dict -}}
{{- $template := required "promotion.live.template é obrigatório: gere os values com deploy/helm/promote.jq" $live.template -}}
{{- if ne (toString $live.name) $svc.name -}}
{{- fail (printf "o estado vivo é de %q, não de %s" (toString $live.name) $svc.name) -}}
{{- end -}}
{{- $public := eq (toString $svc.public) "true" -}}
{{- if ne (toString $live.public) (toString $public) -}}
{{- fail (printf "public de %s: vivo %v, values %v. Promover não muda IAM; alinhe com confirmação humana" $svc.name $live.public $public) -}}
{{- end -}}
{{- $ingress := $svc.ingress | default "all" -}}
{{- if ne (toString $live.ingress) $ingress -}}
{{- fail (printf "ingress de %s: vivo %v, values %s" $svc.name $live.ingress $ingress) -}}
{{- end -}}
{{- $serving := dict -}}
{{- range $live.traffic -}}
{{- if gt (int .percent) 0 -}}
{{- $_ := set $serving .revisionName (add (int (get $serving .revisionName | default 0)) (int .percent)) -}}
{{- end -}}
{{- end -}}
{{- if ne (len $serving) 1 -}}
{{- fail (printf "o tráfego de %s não está 100%% numa revisão (%v): resolva à mão, com confirmação humana" $svc.name $serving) -}}
{{- end -}}
{{- $current := keys $serving | first -}}
{{- if ne (int (get $serving $current)) 100 -}}
{{- fail (printf "o tráfego de %s soma %d%%, não 100%%" $svc.name (int (get $serving $current))) -}}
{{- end -}}
{{- $target := toString (required "promotion.target é obrigatório (main, cNNN, previous ou nome de revisão)" $promotion.target) -}}
{{- $targetRevision := "" -}}
{{- range $live.traffic -}}
{{- if eq (toString .tag) $target -}}
{{- $targetRevision = .revisionName -}}
{{- end -}}
{{- end -}}
{{- if not $targetRevision -}}
{{- range $live.traffic -}}
{{- if eq .revisionName $target -}}
{{- $targetRevision = .revisionName -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- if not $targetRevision -}}
{{- fail (printf "o alvo %q não está no tráfego vivo de %s (use uma tag ou uma revisão listada no describe)" $target $svc.name) -}}
{{- end -}}
{{- if eq $targetRevision $current -}}
{{- fail (printf "%s já recebe 100%% de %s" $targetRevision $svc.name) -}}
{{- end -}}
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: {{ $svc.name }}
  namespace: {{ $root.Values.project.number | quote }}
  labels:
    cloud.googleapis.com/location: {{ $root.Values.project.region }}
    managed-by: helm
  annotations:
    run.googleapis.com/ingress: {{ $ingress }}
    {{- if $public }}
    run.googleapis.com/invoker-iam-disabled: "true"
    {{- end }}
spec:
  template:
    {{- toYaml $template | nindent 4 }}
  traffic:
    - revisionName: {{ $targetRevision }}
      percent: 100
    {{- range $live.traffic }}
    {{- if and .tag (ne (toString .tag) "previous") }}
    - revisionName: {{ .revisionName }}
      percent: 0
      tag: {{ .tag }}
    {{- end }}
    {{- end }}
    - revisionName: {{ $current }}
      percent: 0
      tag: previous
{{- end -}}
