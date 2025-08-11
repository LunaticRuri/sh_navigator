#!/bin/bash

# 통합 서버 시작 스크립트
# 백엔드, 모델, 네트워크 상호작용 서버를 모두 관리

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 스크립트 디렉토리 기준으로 절대 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 로그 파일 정의
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

BACKEND_LOG="$LOG_DIR/backend.log"
MODEL_LOG="$LOG_DIR/model.log"
NETWORK_LOG="$LOG_DIR/network.log"

# PID 파일 정의
PID_DIR="$SCRIPT_DIR/pids"
mkdir -p "$PID_DIR"

BACKEND_PID="$PID_DIR/backend.pid"
MODEL_PID="$PID_DIR/model.pid"
NETWORK_PID="$PID_DIR/network.pid"

# 가상환경 경로
VENV_PATH="/home/namu101/myvenv/bin/activate"

# 서버 경로
BACKEND_PATH="/home/namu101/msga/server_backend"
MODEL_PATH="/home/namu101/msga/server_model"
NETWORK_PATH="/home/namu101/msga/server_network_interaction"

# 도움말 함수
show_help() {
    echo -e "${BLUE}사용법: $0 [옵션]${NC}"
    echo ""
    echo "옵션:"
    echo "  start [backend|model|network|all]  - 서버 시작"
    echo "  stop [backend|model|network|all]   - 서버 중지"
    echo "  restart [backend|model|network|all] - 서버 재시작"
    echo "  status                              - 모든 서버 상태 확인"
    echo "  logs [backend|model|network]        - 서버 로그 보기"
    echo "  help                               - 도움말 표시"
    echo ""
    echo "예시:"
    echo "  $0 start all          # 모든 서버 시작"
    echo "  $0 start backend      # 백엔드 서버만 시작"
    echo "  $0 stop all           # 모든 서버 중지"
    echo "  $0 status             # 서버 상태 확인"
}

# 서버 상태 확인 함수
check_server_status() {
    local service_name=$1
    local pid_file=$2
    local port=$3
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            if nc -z localhost "$port" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ $service_name 실행 중 (PID: $pid, Port: $port)${NC}"
                return 0
            else
                echo -e "${YELLOW}⚠ $service_name 프로세스는 실행 중이지만 포트가 열리지 않음 (PID: $pid)${NC}"
                return 1
            fi
        else
            echo -e "${RED}✗ $service_name 중지됨 (PID 파일 존재하지만 프로세스 없음)${NC}"
            rm -f "$pid_file"
            return 1
        fi
    else
        echo -e "${RED}✗ $service_name 중지됨${NC}"
        return 1
    fi
}

# 백엔드 서버 시작
start_backend() {
    echo -e "${BLUE}백엔드 서버 시작 중...${NC}"
    
    if check_server_status "Backend" "$BACKEND_PID" "8000" > /dev/null 2>&1; then
        echo -e "${YELLOW}백엔드 서버가 이미 실행 중입니다.${NC}"
        return 0
    fi
    
    source "$VENV_PATH"
    cd "$BACKEND_PATH"
    
    nohup gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8000 > "$BACKEND_LOG" 2>&1 &
    echo $! > "$BACKEND_PID"
    
    sleep 3
    if check_server_status "Backend" "$BACKEND_PID" "8000" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 백엔드 서버 시작 완료 (http://localhost:8000)${NC}"
        echo -e "  API docs: http://localhost:8000/docs"
    else
        echo -e "${RED}✗ 백엔드 서버 시작 실패${NC}"
        return 1
    fi
}

# 모델 서버 시작
start_model() {
    echo -e "${BLUE}모델 서버 시작 중...${NC}"
    
    if check_server_status "Model" "$MODEL_PID" "8001" > /dev/null 2>&1; then
        echo -e "${YELLOW}모델 서버가 이미 실행 중입니다.${NC}"
        return 0
    fi
    
    source "$VENV_PATH"
    cd "$MODEL_PATH"
    
    nohup gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8001 > "$MODEL_LOG" 2>&1 &
    echo $! > "$MODEL_PID"
    
    sleep 3
    if check_server_status "Model" "$MODEL_PID" "8001" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 모델 서버 시작 완료 (http://localhost:8001)${NC}"
        echo -e "  API docs: http://localhost:8001/docs"
    else
        echo -e "${RED}✗ 모델 서버 시작 실패${NC}"
        return 1
    fi
}

# 네트워크 상호작용 서버 시작
start_network() {
    echo -e "${BLUE}네트워크 상호작용 서버 시작 중...${NC}"
    
    if check_server_status "Network" "$NETWORK_PID" "8002" > /dev/null 2>&1; then
        echo -e "${YELLOW}네트워크 상호작용 서버가 이미 실행 중입니다.${NC}"
        return 0
    fi
    
    source "$VENV_PATH"
    cd "$NETWORK_PATH"
    
    gunicorn -w 1 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8002 > "$NETWORK_LOG" 2>&1 &
    echo $! > "$NETWORK_PID"
    
    sleep 3
    if check_server_status "Network" "$NETWORK_PID" "8002" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 네트워크 상호작용 서버 시작 완료 (http://localhost:8002)${NC}"
    else
        echo -e "${RED}✗ 네트워크 상호작용 서버 시작 실패${NC}"
        return 1
    fi
}

# 서버 중지 함수
stop_server() {
    local service_name=$1
    local pid_file=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${BLUE}$service_name 서버 중지 중... (PID: $pid)${NC}"
            kill "$pid"
            
            # 5초 대기 후 강제 종료
            for i in {1..5}; do
                if ! ps -p "$pid" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            
            if ps -p "$pid" > /dev/null 2>&1; then
                echo -e "${YELLOW}강제 종료 중...${NC}"
                kill -9 "$pid"
            fi
            
            rm -f "$pid_file"
            echo -e "${GREEN}✓ $service_name 서버 중지 완료${NC}"
        else
            echo -e "${YELLOW}$service_name 서버가 이미 중지되었습니다.${NC}"
            rm -f "$pid_file"
        fi
    else
        echo -e "${YELLOW}$service_name 서버가 실행 중이지 않습니다.${NC}"
    fi
}

# 로그 보기 함수
show_logs() {
    local service=$1
    case $service in
        backend)
            echo -e "${BLUE}=== Backend Server Logs ===${NC}"
            tail -f "$BACKEND_LOG"
            ;;
        model)
            echo -e "${BLUE}=== Model Server Logs ===${NC}"
            tail -f "$MODEL_LOG"
            ;;
        network)
            echo -e "${BLUE}=== Network Server Logs ===${NC}"
            tail -f "$NETWORK_LOG"
            ;;
        *)
            echo -e "${RED}잘못된 서비스 이름입니다. [backend|model|network] 중 선택하세요.${NC}"
            ;;
    esac
}

# 메인 로직
case ${1:-help} in
    start)
        case ${2:-all} in
            backend)
                start_backend
                ;;
            model)
                start_model
                ;;
            network)
                start_network
                ;;
            all)
                echo -e "${GREEN}=== 모든 서버 시작 ===${NC}"
                start_backend
                start_model
                start_network
                echo ""
                echo -e "${GREEN}=== 서버 상태 ===${NC}"
                check_server_status "Backend" "$BACKEND_PID" "8000"
                check_server_status "Model" "$MODEL_PID" "8001"
                check_server_status "Network" "$NETWORK_PID" "8002"
                ;;
            *)
                echo -e "${RED}잘못된 서비스 이름입니다.${NC}"
                show_help
                ;;
        esac
        ;;
    stop)
        case ${2:-all} in
            backend)
                stop_server "Backend" "$BACKEND_PID"
                ;;
            model)
                stop_server "Model" "$MODEL_PID"
                ;;
            network)
                stop_server "Network" "$NETWORK_PID"
                ;;
            all)
                echo -e "${GREEN}=== 모든 서버 중지 ===${NC}"
                stop_server "Backend" "$BACKEND_PID"
                stop_server "Model" "$MODEL_PID"
                stop_server "Network" "$NETWORK_PID"
                ;;
            *)
                echo -e "${RED}잘못된 서비스 이름입니다.${NC}"
                show_help
                ;;
        esac
        ;;
    restart)
        case ${2:-all} in
            backend)
                stop_server "Backend" "$BACKEND_PID"
                sleep 2
                start_backend
                ;;
            model)
                stop_server "Model" "$MODEL_PID"
                sleep 2
                start_model
                ;;
            network)
                stop_server "Network" "$NETWORK_PID"
                sleep 2
                start_network
                ;;
            all)
                echo -e "${GREEN}=== 모든 서버 재시작 ===${NC}"
                stop_server "Backend" "$BACKEND_PID"
                stop_server "Model" "$MODEL_PID"
                stop_server "Network" "$NETWORK_PID"
                sleep 2
                start_backend
                start_model
                start_network
                ;;
            *)
                echo -e "${RED}잘못된 서비스 이름입니다.${NC}"
                show_help
                ;;
        esac
        ;;
    status)
        echo -e "${GREEN}=== 서버 상태 확인 ===${NC}"
        check_server_status "Backend" "$BACKEND_PID" "8000"
        check_server_status "Model" "$MODEL_PID" "8001"
        check_server_status "Network" "$NETWORK_PID" "8002"
        ;;
    logs)
        show_logs "$2"
        ;;
    help|*)
        show_help
        ;;
esac
