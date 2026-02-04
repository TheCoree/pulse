version = 'v1'

art = f"""
▄▄▄▄  ▄▄ ▄▄ ▄▄     ▄▄▄▄ ▄▄▄▄▄   ▄▄▄▄▄▄ ▄▄▄▄▄▄ ▄▄   ▄▄ {version}
██▄█▀ ██ ██ ██    ███▄▄ ██▄▄      ██     ██   ██▀▄▀██ 
██    ▀███▀ ██▄▄▄ ▄▄██▀ ██▄▄▄     ██     ██   ██   ██     server
                                                      """


def print_start_message() -> None:
    print(art)
    print(f'[+] Pulse TTM {version} now started | made by corede (https://github.com/TheCoree)')
    print('-' * 75)


def print_end_message() -> None:
    print(f'[-] Pulse TTM {version} has been stoped. Bye!')
