import json
import re
from app.agents.base_agent import BaseAgent


class DatabaseSchemaAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="database_schema")

    def get_system_prompt(self) -> str:
        return """You are a senior database architect specializing in relational database design.

Your responsibilities:
1. Design normalized database schemas (3NF)
2. Define tables with appropriate columns and data types
3. Specify primary keys, foreign keys, and indexes
4. Consider query performance and scalability
5. Add constraints (UNIQUE, NOT NULL, CHECK)
6. Define relationships (one-to-many, many-to-many, one-to-one)

CRITICAL: Return ONLY valid JSON. No markdown, no explanation outside the JSON.

OUTPUT FORMAT (exact structure):
{
  "database_type": "PostgreSQL|MySQL|SQLite",
  "tables": [
    {
      "name": "table_name",
      "description": "What this table stores",
      "columns": [
        {
          "name": "column_name",
          "type": "VARCHAR(255)|INTEGER|BIGINT|DECIMAL(10,2)|TIMESTAMP|BOOLEAN|TEXT|JSON",
          "nullable": false,
          "primary_key": false,
          "unique": false,
          "default": null,
          "foreign_key": {
            "table": "other_table",
            "column": "id",
            "on_delete": "CASCADE|SET NULL|RESTRICT"
          }
        }
      ],
      "indexes": [
        {
          "name": "idx_name",
          "columns": ["col1", "col2"],
          "unique": false
        }
      ]
    }
  ],
  "relationships": [
    {
      "type": "one-to-many|many-to-many|one-to-one",
      "from_table": "table1",
      "to_table": "table2",
      "description": "Relationship explanation"
    }
  ],
  "notes": "Key design decisions and performance considerations"
}

Best practices:
- Always have an auto-incrementing primary key (id)
- Use created_at and updated_at timestamps
- Index foreign keys
- Use appropriate data types (don't use TEXT for everything)
- Consider soft deletes (deleted_at column) vs hard deletes"""

    def parse_output(self, raw_content: str) -> dict:
        """Extract schema JSON and generate SQL"""
        try:
            schema = json.loads(raw_content)
        except json.JSONDecodeError:
            json_match = re.search(r'```(?:json)?\n?(.*?)```', raw_content, re.DOTALL)
            if json_match:
                schema = json.loads(json_match.group(1))
            else:
                json_match = re.search(r'\{.*\}', raw_content, re.DOTALL)
                if json_match:
                    schema = json.loads(json_match.group(0))
                else:
                    return {"error": "No valid JSON found", "raw_output": raw_content}

        # Generate SQL DDL statements
        sql_statements = self._generate_sql(schema)

        return {
            "schema": schema,
            "table_count": len(schema.get("tables", [])),
            "sql_ddl": sql_statements,
            "database_type": schema.get("database_type", "PostgreSQL"),
        }

    def _generate_sql(self, schema: dict) -> str:
        """Generate CREATE TABLE statements from schema"""
        statements = []
        db_type = schema.get("database_type", "PostgreSQL")

        for table in schema.get("tables", []):
            cols = []
            for col in table.get("columns", []):
                col_def = f'  "{col["name"]}" {col["type"]}'
                
                if col.get("primary_key"):
                    if db_type == "PostgreSQL":
                        col_def = f'  "{col["name"]}" SERIAL PRIMARY KEY'
                    else:
                        col_def += " PRIMARY KEY AUTO_INCREMENT"
                else:
                    if not col.get("nullable", True):
                        col_def += " NOT NULL"
                    if col.get("unique"):
                        col_def += " UNIQUE"
                    if "default" in col and col["default"] is not None:
                        col_def += f" DEFAULT {col['default']}"
                    if "foreign_key" in col:
                        fk = col["foreign_key"]
                        col_def += f' REFERENCES "{fk["table"]}"("{fk["column"]}")'
                        if "on_delete" in fk:
                            col_def += f' ON DELETE {fk["on_delete"]}'
                
                cols.append(col_def)
            
            create_table = f'CREATE TABLE "{table["name"]}" (\n'
            create_table += ",\n".join(cols)
            create_table += "\n);"
            statements.append(create_table)
            
            # Add indexes
            for idx in table.get("indexes", []):
                idx_cols = ", ".join(f'"{c}"' for c in idx["columns"])
                unique_keyword = "UNIQUE " if idx.get("unique") else ""
                idx_sql = f'CREATE {unique_keyword}INDEX "{idx["name"]}" ON "{table["name"]}" ({idx_cols});'
                statements.append(idx_sql)
        
        return "\n\n".join(statements)