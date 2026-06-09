{{/*
Expand the name of the chart.
*/}}
{{- define "maybot.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Fully qualified app name.
*/}}
{{- define "maybot.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "maybot.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "maybot.labels" -}}
helm.sh/chart: {{ include "maybot.chart" . }}
{{ include "maybot.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels (control center).
*/}}
{{- define "maybot.selectorLabels" -}}
app.kubernetes.io/name: {{ include "maybot.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Control-center component labels.
*/}}
{{- define "maybot.controlCenter.labels" -}}
{{ include "maybot.labels" . }}
app.kubernetes.io/component: control-center
{{- end }}

{{- define "maybot.controlCenter.selectorLabels" -}}
{{ include "maybot.selectorLabels" . }}
app.kubernetes.io/component: control-center
{{- end }}

{{/*
Agent component labels.
*/}}
{{- define "maybot.agent.labels" -}}
{{ include "maybot.labels" . }}
app.kubernetes.io/component: agent
{{- end }}

{{- define "maybot.agent.selectorLabels" -}}
{{ include "maybot.selectorLabels" . }}
app.kubernetes.io/component: agent
{{- end }}

{{/*
Name of the Secret holding the tokens/keys.
*/}}
{{- define "maybot.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "maybot.fullname" .) }}
{{- end }}
{{- end }}

{{/*
Name of the PVC for /data.
*/}}
{{- define "maybot.pvcName" -}}
{{- if .Values.persistence.existingClaim }}
{{- .Values.persistence.existingClaim }}
{{- else }}
{{- printf "%s-data" (include "maybot.fullname" .) }}
{{- end }}
{{- end }}
