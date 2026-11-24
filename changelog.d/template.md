{#- The changelog is for users: each entry says what changed for them, without the issue it
came from. A fragment is still named after its issue (PM-<n>.fixed.md), only so that two pull
requests never write the same file. Adapted from towncrier's default Markdown template. -#}
{%- macro heading(level) -%}
    {{- "#" * ( header_prefix | length + level -1 ) }}
{%- endmacro -%}
{%- set newline = "\n" -%}
{%- if render_title %}
    {{- heading(1) ~ " " ~ versiondata.version ~ " (" ~ versiondata.date ~ ")" ~ newline }}
{%- endif %}
{{- newline }}
{%- for section, _ in sections.items() %}
    {%- if section %}
        {{- newline ~ heading(2) ~ " " ~ section ~ newline ~ newline }}
    {%- endif %}
    {%- if sections[section] %}
        {%- for category, val in definitions.items() if category in sections[section] %}
            {{- heading(3 if section else 2) ~ " " ~ definitions[category]['name'] ~ newline ~ newline }}
            {%- for text, values in sections[section][category].items() %}
                {{- "- " ~ text ~ newline }}
            {%- endfor %}
            {{- newline }}
        {%- endfor %}
    {%- else %}
        {{- "No significant changes." ~ newline * 2 }}
    {%- endif %}
{%- endfor %}
{{- newline -}}
