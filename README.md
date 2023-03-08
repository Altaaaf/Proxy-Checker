# Proxy-Checker
Fast, lightweight asynchronous proxy checker that checks HTTP, HTTPS, SOCKS4, SOCKS5 proxies 

![usage](https://user-images.githubusercontent.com/75543185/223733990-f0e694af-6fca-46aa-b14f-db8f2acda7b7.png)



## Get started

``` {.sourceCode}
Run this command to install required packages

pip install -r requirements.txt

After installing required packages, run main.py
```

## Features

- [x] Supported protocols (HTTP, HTTPS, SOCKS4, SOCKS5)
- [x] Filter duplicate and invalid proxies
- [x] Retry if proxy times out with delay
- [x] Asynchronous


## Command line usage

--type refers to proxy type, valid options above

--file refers to file path to proxies

--max_tasks refers to maximum concurrent tasks 

``` {.sourceCode}
main.py --type HTTPS --file proxies.txt --max_tasks 100
```
