{{/*
URI da imagem: tag (repo/nome:tag) ou digest (repo/nome@sha256:...).
*/}}
{{- define "bussola.image" -}}
{{- $image := toString .service.image -}}
{{- $separator := ternary "@" ":" (hasPrefix "sha256:" $image) -}}
{{- printf "%s/%s%s%s" .root.Values.imageRepository .service.name $separator $image -}}
{{- end -}}

{{/*
Manifesto Knative de um serviço Cloud Run, aplicado com
`gcloud run services replace`.

Regras de plataforma validadas aqui:
- a revisão nova sai sempre com 0% de tráfego e tag `main` (última revisão
  da main, deploy automático) ou cNNN (ciclo); só o 007 move tráfego;
- o tráfego mantido soma 100% e não reutiliza a tag da revisão nova;
- exceção: `create: true` cria o serviço, e a primeira revisão recebe 100%
  porque não há outra. Só vale sem tráfego mantido, é manual e exige
  confirmação humana (deploy/helm/README.md);
- nada com cara de segredo vai em env: segredo só por secretEnv (Secret
  Manager).
O replace não mexe em bindings de IAM. Sem `public: true`, o serviço exige
roles/run.invoker; com ele, a checagem de invoker fica desligada
(run.googleapis.com/invoker-iam-disabled). Só o BFF é público, com
confirmação humana.
*/}}
{{- define "bussola.cloudRunService" -}}
{{- $root := .root -}}
{{- $svc := .service -}}
{{- $tag := toString (required "release.tag é obrigatório (main ou cNNN)" $root.Values.release.tag) -}}
{{- /* cNNN-<rótulo> (ex.: c007-bad): revisão de teste de um ciclo, sempre 0%. */ -}}
{{- if not (regexMatch "^(main|c[0-9]{3}(-[a-z]{1,10})?)$" $tag) -}}
{{- fail (printf "release.tag deve ser main ou cNNN (ou cNNN-<rótulo>, ex.: c007-bad), veio %q" $tag) -}}
{{- end -}}
{{- $suffix := toString (required "release.revisionSuffix é obrigatório" $root.Values.release.revisionSuffix) -}}
{{- if not (regexMatch "^[a-z0-9]([a-z0-9-]*[a-z0-9])?$" $suffix) -}}
{{- fail (printf "release.revisionSuffix aceita só minúsculas, dígitos e hífen, veio %q" $suffix) -}}
{{- end -}}
{{- $revision := printf "%s-%s" $svc.name $suffix -}}
{{- if gt (len $revision) 63 -}}
{{- fail (printf "nome de revisão com mais de 63 caracteres: %s" $revision) -}}
{{- end -}}
{{- $_ := required (printf "services.<nome>.image é obrigatório para %s" $svc.name) $svc.image -}}
{{- $total := 0 -}}
{{- range $svc.traffic -}}
{{- $total = add $total .percent -}}
{{- if eq (toString .tag) $tag -}}
{{- fail (printf "a tag %s já está na revisão %s de %s" $tag .revisionName $svc.name) -}}
{{- end -}}
{{- end -}}
{{- $create := eq (toString $svc.create) "true" -}}
{{- if $create -}}
{{- if $svc.traffic -}}
{{- fail (printf "create só vale para serviço novo: %s já tem tráfego mantido" $svc.name) -}}
{{- end -}}
{{- else if ne (int $total) 100 -}}
{{- fail (printf "o tráfego mantido de %s deve somar 100%%, soma %d%%" $svc.name (int $total)) -}}
{{- end -}}
{{- range $name, $_ := $svc.env -}}
{{- if regexMatch "(KEY|TOKEN|SECRET|PASSWORD)" $name -}}
{{- fail (printf "%s parece segredo: declare em secretEnv de %s" $name $svc.name) -}}
{{- end -}}
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
    run.googleapis.com/ingress: {{ $svc.ingress | default "all" }}
    {{- if eq (toString $svc.public) "true" }}
    run.googleapis.com/invoker-iam-disabled: "true"
    {{- end }}
spec:
  template:
    metadata:
      name: {{ $revision }}
      labels:
        release-tag: {{ $tag }}
      annotations:
        autoscaling.knative.dev/maxScale: {{ $svc.maxInstances | toString | quote }}
        run.googleapis.com/startup-cpu-boost: "true"
    spec:
      serviceAccountName: {{ $root.Values.serviceAccount }}
      containerConcurrency: {{ $svc.concurrency | default 80 }}
      timeoutSeconds: {{ $svc.timeoutSeconds | default 300 }}
      containers:
        - image: {{ include "bussola.image" (dict "root" $root "service" $svc) }}
          ports:
            - name: http1
              containerPort: 8080
          resources:
            limits:
              cpu: {{ $svc.cpu | quote }}
              memory: {{ $svc.memory }}
          env:
            {{- range $name, $value := $svc.env }}
            - name: {{ $name }}
              value: {{ $value | toString | quote }}
            {{- end }}
            {{- range $name, $ref := $svc.secretEnv }}
            - name: {{ $name }}
              valueFrom:
                secretKeyRef:
                  name: {{ $ref.secret }}
                  key: {{ $ref.version | default "latest" | toString | quote }}
            {{- end }}
  traffic:
    {{- range $svc.traffic }}
    - revisionName: {{ .revisionName }}
      percent: {{ .percent }}
      {{- with .tag }}
      tag: {{ . }}
      {{- end }}
    {{- end }}
    - revisionName: {{ $revision }}
      percent: {{ ternary 100 0 $create }}
      tag: {{ $tag }}
{{- end -}}
