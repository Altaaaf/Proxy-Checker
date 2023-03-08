import pathlib
import datetime
import ssl
import os
import argparse
import asyncio
import time
from typing import List
import aiohttp
from aiohttp_socks import ProxyConnector, ProxyType
import aiofiles


class ProxyChecker:
    def __init__(self, request_timeout=5, max_retry=1, retry_delay=3):
        """
        Initialize a ProxyChecker object.

        Args:
            request_timeout (int): The timeout for each HTTP request, in seconds (default 5).
            max_retry (int): The maximum number of times to retry a request that fails due to a transient error (default 1).
            retry_delay (int): The delay between retry attempts, in seconds (default 3).

        Returns:
            None.
        """
        self.__request_timeout = request_timeout
        self.__max_retry = max_retry
        self.__retry_delay = retry_delay
        self.__total_proxies_checked = 0
        self.__good_proxies = 0
        self.__proxies_checked_per_minute = 0
        self.__start_time = time.perf_counter()
        self.__good_proxy_file_path = pathlib.Path(
            f'proxy_check_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.txt')
        if not self.__good_proxy_file_path.exists():
            with open(self.__good_proxy_file_path, encoding='utf-8', mode='w') as f:
                pass

        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    async def save_proxy(self, proxy: str) -> None:
        """
        Save a good proxy to a file in a thread-safe manner.

        Args:
            proxy: A string representing the proxy to be saved.

        Returns:
            None

        Raises:
            IOError: If there is an error writing to the file.

        """
        try:
            async with aiofiles.open(self.__good_proxy_file_path, mode='a', encoding='utf-8') as outfile:
                await outfile.write(f"{proxy}\n")
        except IOError as e:
            print(f"ERROR SAVING PROXY | {e}")

    async def read_proxy_file(self, filepath: str) -> List[str]:
        """
        Read proxies from a file and return a list of unique proxy strings.

        Args:
            filepath: Path to the file containing the proxies.

        Returns:
            A list of unique proxy strings.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is empty or contains invalid proxy strings.

        """
        proxies = []
        try:
            async with aiofiles.open(filepath, encoding='utf-8', mode="r") as proxy_file:
                async for line in proxy_file:
                    line = line.strip()
                    if ":" in line:
                        split_line = line.split(":")
                        if len(split_line) == 2 or len(split_line) == 4:
                            proxies.append(line)
                if not proxies:
                    raise ValueError(
                        "The file does not contain any valid proxies.")
                return list(set(proxies))
        except FileNotFoundError:
            raise FileNotFoundError(f"The file {filepath} does not exist.")
        except ValueError as e:
            raise ValueError(
                f"An error occurred while reading the proxy file: {e}")

    async def check_proxy(self, proxy: str, proxy_type: str, semaphore: asyncio.Semaphore) -> None:
        """
        Checks if a given proxy is working by making a request to https://api.ipify.org/

        Args:
            proxy: A string representing the proxy in the format <host>:<port>[:<username>:<password>].
            proxy_type: A string representing the type of the proxy (HTTP, HTTPS, SOCKS4, SOCKS5).
            timeout: An integer representing the timeout value for the request in seconds.
            semaphore: An asyncio Semaphore object used to limit the number of concurrent requests.

        Returns:
            None.

        Raises:
            ValueError: If the proxy type is invalid.
            aiohttp.ClientError: If there is an error with the client session.
            Exception: For any other errors encountered.
        """
        retry_count = 0
        while retry_count <= self.__max_retry:
            try:
                async with semaphore:
                    proxy_split = proxy.split(":")
                    host = proxy_split[0]
                    port = proxy_split[1]
                    username = None if len(
                        proxy_split) != 4 else proxy_split[2]
                    password = None if len(
                        proxy_split) != 4 else proxy_split[3]
                    aio_proxy_type = None
                    if proxy_type in ["HTTP", "HTTPS"]:
                        aio_proxy_type = ProxyType.HTTP
                    elif proxy_type == "SOCKS4":
                        aio_proxy_type = ProxyType.SOCKS4
                    elif proxy_type == "SOCKS5":
                        aio_proxy_type = ProxyType.SOCKS5
                    else:
                        raise ValueError("Invalid proxy type")
                    async with aiohttp.ClientSession(
                            connector=ProxyConnector(proxy_type=aio_proxy_type,
                                                     host=host,
                                                     port=port,
                                                     username=username,
                                                     password=password,
                                                     rdns=True,
                                                     proxy_ssl=None,
                                                     ssl=self.ssl_context)) as session:
                        request_start_time = time.monotonic()
                        async with session.get("https://api.ipify.org/",
                                               timeout=self.__request_timeout,
                                               headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}) as response:
                            status = response.status
                            response_time = int(
                                (time.monotonic() - request_start_time))

                            if status == 200:
                                print(
                                    f"[SUCCESS] {proxy} - {response_time} seconds response time")
                                await self.save_proxy(proxy)
                                self.__good_proxies += 1
                            else:
                                print(
                                    f"[FAILURE] {proxy} - {response_time} seconds response time")
                            return
            except asyncio.TimeoutError:
                print(
                    f"[FAILURE] {proxy} - failed to connect in {self.__request_timeout} seconds")
                retry_count += 1
                await asyncio.sleep(self.__retry_delay)
            except (aiohttp.ClientError, ValueError) as err:
                print(f"[FAILURE] {proxy} - {err}")
                retry_count += 1
                await asyncio.sleep(self.__retry_delay)
            except Exception as err:
                print(f"[FAILURE] {proxy} - {type(err).__name__}: {err}")
                retry_count += 1
                await asyncio.sleep(self.__retry_delay)
            finally:
                self.__total_proxies_checked += 1
                self.__proxies_checked_per_minute = round(
                    self.__total_proxies_checked / ((time.perf_counter() - self.__start_time) / 60))
                os.system(
                    f"title Proxy Checker - Checked: {self.__total_proxies_checked} - Good: {self.__good_proxies} - Proxies/Min: {self.__proxies_checked_per_minute}")

        print(f"[FAILURE] {proxy} - exceeded maximum retries")

    async def main(self, proxy_type: str, proxy_file: str, max_concurrent_tasks: int) -> None:
        """
        Main function to check proxies concurrently using asyncio.

        Args:
            proxy_type (str): Type of proxy. Must be one of "http", "https", "socks4", "socks5".
            proxy_file (str): Path to the file containing proxies.
            max_concurrent_tasks (int): Maximum number of concurrent tasks.

        Returns:
            None.

        Raises:
            ValueError: If an invalid proxy type is passed.

        """
        proxies = await self.read_proxy_file(proxy_file)
        initial_start_time = time.time()
        semaphore = asyncio.Semaphore(max_concurrent_tasks)
        tasks = [self.check_proxy(proxy, proxy_type, semaphore)
                 for proxy in proxies]
        await asyncio.gather(*tasks)

        input(f"Proxy Checker - Checked: {self.__total_proxies_checked} - Good: {self.__good_proxies} - Proxies/Min: {self.__proxies_checked_per_minute} - Elapsed time: {int((time.time() - initial_start_time))} seconds")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("-t", "--type", type=str,
                            help="Enter proxy type (HTTP/HTTPS/SOCKS4/SOCKS5)")
        parser.add_argument("-f", "--file", type=str,
                            help="Enter proxy file path")
        parser.add_argument("-m", "--max_tasks", type=int,
                            help="Enter max concurrent tasks")
        args = parser.parse_args()

        proxytype = args.type if args.type else input(
            "Enter proxy type (HTTP/HTTPS/SOCKS4/SOCKS5): ")
        proxy_file_path = args.file or input("Enter proxy file path: ")
        max_concurrent_tasks_ = args.max_tasks or int(
            input("Enter max concurrent tasks: "))

        proxychecker = ProxyChecker()
        asyncio.run(proxychecker.main(proxytype.upper(),
                    proxy_file_path, max_concurrent_tasks_))
    except Exception as e:
        print(f"An error occurred: {e}")
