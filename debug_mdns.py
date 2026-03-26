import asyncio
from zeroconf import Zeroconf, ServiceBrowser, ServiceListener

class MyListener(ServiceListener):
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info:
            addresses = info.parsed_addresses()
            print(f"FOUND: {name} ({type_})")
            print(f"  - Host: {addresses[0] if addresses else 'Unknown'}:{info.port}")
            print(f"  - Properties: {info.properties}")

    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        pass

async def scan():
    try:
        zeroconf = Zeroconf()
    except PermissionError as e:
        print("mDNS scan could not start because the network socket could not be opened.")
        print("On macOS, this usually means the current environment is blocking multicast/bind access.")
        print(f"Details: {e}")
        return

    listener = MyListener()
    
    print("Scanning for common printer services...")
    services = [
        "_octoprint._tcp.local.",
        "_moonraker._tcp.local.",
        "_klipper._tcp.local.",
        "_http._tcp.local.",
        "_ipp._tcp.local.",
        "_printer._tcp.local."
    ]
    
    try:
        browsers = []
        for s in services:
            browsers.append(ServiceBrowser(zeroconf, s, listener))

        print("Listening for 10 seconds...")
        await asyncio.sleep(10)
    finally:
        zeroconf.close()

if __name__ == "__main__":
    asyncio.run(scan())
