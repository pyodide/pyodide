{% import 'common.rst' as common %}

.. js:attribute:: {{ name }}{{ '?' if is_optional else '' }}

   {{ common.deprecated(deprecated)|indent(3) }}

   {% if type -%}
      .. rst-class:: js attribute type

          type: {{ type|indent(3) }}
   {%- endif %}

   {% if description -%}
     {{ description|indent(3) }}
   {%- endif %}

   {{ common.examples(examples)|indent(3) }}

   {{ content|indent(3) }}

   {{ common.see_also(see_also)|indent(3) }}
