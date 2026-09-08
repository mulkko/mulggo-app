# 실제 DB(Supabase)에서 테이블 구조를 읽어와 schema.sql에 붙여넣을 CREATE TABLE 초안을 출력.
# schema.sql이 실제 운영 DB보다 뒤처져 있을 때(예: 다른 사람이 Supabase에서 직접 테이블을
# 만든 경우) 문서화 용도로 사용. 출력된 걸 그대로 schema.sql에 붙여넣고 한글 주석만 달아주면 됨.
#
# 사용법: python -m backend.db.describe_table <테이블명>

import sys

from backend.db.connection import get_connection

_TYPE_MAP = {
    "character varying": "VARCHAR",
    "text": "TEXT",
    "bigint": "BIGINT",
    "integer": "INT",
    "boolean": "BOOLEAN",
    "jsonb": "JSONB",
    "timestamp with time zone": "TIMESTAMPTZ",
    "date": "DATE",
    "numeric": "NUMERIC",
}


def describe(table_name: str) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        columns = cursor.fetchall()
        if not columns:
            print(f"'{table_name}' 테이블을 찾을 수 없습니다.")
            return

        cursor.execute(
            """
            SELECT tc.constraint_type, kcu.column_name, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name AND tc.constraint_type = 'FOREIGN KEY'
            WHERE tc.table_name = %s
            """,
            (table_name,),
        )
        constraints = cursor.fetchall()
    finally:
        connection.close()

    pk_cols = {c[1] for c in constraints if c[0] == "PRIMARY KEY"}
    fk_map = {c[1]: (c[2], c[3]) for c in constraints if c[0] == "FOREIGN KEY"}

    print(f"CREATE TABLE IF NOT EXISTS {table_name} (")
    lines = []
    for name, dtype, maxlen, nullable, default in columns:
        sql_type = _TYPE_MAP.get(dtype, dtype.upper())
        if maxlen and sql_type == "VARCHAR":
            sql_type = f"VARCHAR({maxlen})"

        parts = [name]
        if default and "nextval" in default:
            parts.append("BIGSERIAL")
        else:
            parts.append(sql_type)
            if default:
                parts.append(f"DEFAULT {default}")

        if name in pk_cols:
            parts.append("PRIMARY KEY")
        elif nullable == "NO":
            parts.append("NOT NULL")

        if name in fk_map:
            foreign_table, foreign_column = fk_map[name]
            parts.append(f"REFERENCES {foreign_table}({foreign_column})")

        lines.append("    " + " ".join(parts))

    print(",\n".join(lines))
    print(");")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python -m backend.db.describe_table <테이블명>")
        sys.exit(1)
    describe(sys.argv[1])
