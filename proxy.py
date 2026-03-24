from config import LOGIN_PROXY, PASSWORD_PROXY
from colorama import init, Fore
import os
import glob


class Proxy:
    @staticmethod
    async def get_proxies(config_path="/opt/projects/piwi247/proxy/config"):
        proxies = []

        for file_path in glob.glob(f"{config_path}/*/*.conf"):
            filename = os.path.basename(file_path).replace(".conf", "")
            parts = filename.split("_")

            if len(parts) == 5:  # IP (4 части) + порт
                host = ".".join(parts[:4])
                port = parts[4]

                proxy_data = {
                    "host": host,
                    "port": port,
                    "protocol": "socks5",
                    "username": LOGIN_PROXY,
                    "password": PASSWORD_PROXY,
                }

                proxies.append(proxy_data)

        print("Количество прокси:", len(proxies))
        return proxies
