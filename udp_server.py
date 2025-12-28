import socket

def start_udp_relay():
    # 创建 UDP 套接字
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # 监听所有网卡，端口 10000 (可修改)
    RELAY_PORT = 10000
    server.bind(('0.0.0.0', RELAY_PORT))
    print(f"UDP 中转服务器已启动，正在监听端口 {RELAY_PORT}...")
    print("等待玩家接入 (模式: 自动配对前两个连接者)...")

    # 存储连接的玩家地址 [(ip, port), (ip, port)]
    clients = []

    while True:
        try:
            data, addr = server.recvfrom(4096)
            
            # 1. 注册新玩家
            if addr not in clients:
                if len(clients) < 2:
                    clients.append(addr)
                    print(f"玩家加入: {addr} (当前人数: {len(clients)}/2)")
                    # 如果是第二个玩家加入，通知双方可以开始了（可选，BattleApp本身有握手逻辑）
                else:
                    # 房间满了，忽略或打印提示
                    # print(f"房间已满，忽略来自 {addr} 的数据")
                    pass

            # 2. 转发逻辑
            if len(clients) == 2:
                # 确定发送目标：如果是 clients[0] 发来的，就发给 clients[1]，反之亦然
                if addr == clients[0]:
                    target = clients[1]
                elif addr == clients[1]:
                    target = clients[0]
                else:
                    continue # 第三者，忽略

                server.sendto(data, target)
        
        except Exception as e:
            print(f"转发错误: {e}")

if __name__ == "__main__":
    start_udp_relay()