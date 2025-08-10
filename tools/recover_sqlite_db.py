import sqlite3
import subprocess
import os

def recover_sqlite_db(broken_db_path, healthy_db_path):
    """
    손상된 SQLite DB를 복구합니다 (Dump & Recreate 방식).
    """
    if not os.path.exists(broken_db_path):
        print(f"오류: '{broken_db_path}' 파일을 찾을 수 없습니다.")
        return False

    # 1. SQL 덤프 파일 생성
    sql_dump_path = "recovery_temp.sql"
    try:
        # sqlite3 broken.db .dump > recovery.sql 실행
        with open(sql_dump_path, 'w') as f_dump:
            subprocess.run(
                ["sqlite3", broken_db_path, ".dump"], 
                stdout=f_dump, 
                check=True # 오류 발생 시 예외 발생
            )
        print(f"'{sql_dump_path}' 파일로 데이터 덤프 성공.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"데이터 덤프 중 오류 발생: {e}")
        # 덤프 파일이 생성되었을 수 있으니 정리
        if os.path.exists(sql_dump_path):
            os.remove(sql_dump_path)
        return False

    # 2. 새 DB에 덤프 파일 임포트
    try:
        # sqlite3 new.db < recovery.sql 실행
        with open(sql_dump_path, 'r') as f_dump:
            subprocess.run(
                ["sqlite3", healthy_db_path],
                stdin=f_dump,
                check=True
            )
        print(f"'{healthy_db_path}'에 데이터 복구 성공.")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"데이터 복구 중 오류 발생: {e}")
        return False
    finally:
        # 임시 덤프 파일 삭제
        if os.path.exists(sql_dump_path):
            os.remove(sql_dump_path)
            
    return True

# --- 사용 예시 ---
BROKEN_DB = './data/db/books.db'
HEALTHY_DB = './data/db/books_recovered.db'

# # 실제 실행 전, 테스트용으로 빈 손상 파일 생성 (실제 상황에서는 이 부분 필요 없음)
# with open(BROKEN_DB, 'w') as f:
#     f.write("This is a fake malformed db")

# # 복구 함수 실행 (실제로는 손상된 DB 파일 경로를 넣으세요)
if recover_sqlite_db(BROKEN_DB, HEALTHY_DB):
    print("\n복구 완료! 이제 'my_recovered_app.db' 파일을 사용하세요.")
else:
    print("\n복구 실패.")