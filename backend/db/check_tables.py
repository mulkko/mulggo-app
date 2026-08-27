# 현재 로그인 계정의 테이블 목록과 임의 테이블의 첫 행을 출력하는 확인용 스크립트

from connection import get_connection


def list_tables(cursor):
    cursor.execute("SELECT table_name FROM user_tables ORDER BY table_name")
    return [row[0] for row in cursor.fetchall()]


def fetch_first_row(cursor, table_name):
    cursor.execute(f"SELECT * FROM {table_name} WHERE ROWNUM = 1")
    columns = [col[0] for col in cursor.description]
    row = cursor.fetchone()
    return columns, row


if __name__ == "__main__":
    connection = get_connection()
    try:
        cursor = connection.cursor()

        tables = list_tables(cursor)
        print(f"테이블 목록 ({len(tables)}개)")
        for name in tables:
            print(f"- {name}")

        if tables:
            target_table = tables[0]
            columns, row = fetch_first_row(cursor, target_table)

            print(f"\n[{target_table}] 첫 번째 행")
            if row is None:
                print("(데이터 없음)")
            else:
                for col, value in zip(columns, row):
                    print(f"{col}: {value}")
        else:
            print("테이블이 없습니다.")
    finally:
        connection.close()
