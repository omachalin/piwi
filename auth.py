import requests, time, json, re
from config import (
    LOGIN_ACCOUNT_PIWI, PASSWORD_ACCOUNT_PIWI, API_PIWI_URL, API_TENDER_88_URL, MAIN_SERVER_URL, PASSWORD_ACCOUNT_EMAIL
)
from imap import SimpleMailClient

class PiwiAuth:
    def __init__(self):
        self.email = LOGIN_ACCOUNT_PIWI
        self.password = PASSWORD_ACCOUNT_PIWI
        self.referrer = 'https://www.piwi247.com/'
        self.base_url = API_PIWI_URL
        self.session = requests.Session()
        self.token_pinnacle = None
        self.api_token = None

        if self.login():
            self.get_pinnacle_data()
            self.get_auth_token()
            self.get_balance()
            self.save_session_to_server()

    def save_session_to_server(self):
        cookies_dict = {cookie.name: cookie.value for cookie in self.session.cookies}
        data = {
            'code': 'token',
            'value': json.dumps(cookies_dict)
        }

        requests.post(f"{MAIN_SERVER_URL}/setpinnjsonsettings", data=data, verify=False)

    def get_session(self):
        return self.session

    def login(self):
        url = f"{self.base_url}/api/users/login"
        headers = {
            "accept": "application/json",
            "accept-language": "ru,en;q=0.9",
            "content-type": "application/json",
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="130", "YaBrowser";v="24.12", "Not?A_Brand";v="99", "Yowser";v="2.5"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "referer": self.referrer
        }

        data = {
            "email": self.email,
            "loginType": 1,
            "password": self.password,
            "remember": True,
            "username": self.email,
        }


        response = self.session.post(url, headers=headers, json=data)

        data['purpose'] = 'login'
        data['signupType'] = 1

        response = self.session.post(f"{self.base_url}/api/sms-code/get-code", headers=headers, json=data)
        time.sleep(10)
        response_data = response.json()

        if response_data['error']:
            print("Login failed.")
            return False

        print('Ожидаем 10 секунд...')
        time.sleep(10)

        client = SimpleMailClient(login=self.email, password=PASSWORD_ACCOUNT_EMAIL)
        client.connect()
        body = client.fetch_latest_unseen()
        client.logout()
        match = re.search(r'\b\d{6}\b', body)
        if not match:
            raise Exception('Ошибка при получении кода')

        code = match.group()

        print('Verification code: ', code)

        params = {
            "email": self.email,
            "password": self.password,
            "loginType": 1,
            "remember": False,
            "username": self.email,
            "purpose": "login",
            "signupType": 1,
            "verificationCode": code
        }

        response = self.session.post(f"{self.base_url}/api/users/verify-otp", headers=headers, json=params)
        response_data = response.json()

        # Получаем токены
        self.api_token = response_data['data']['token']['api']['access_token']
        self.token_pinnacle = response_data['data']['token']['pinnacle']['token']
        print("Login successful.")
        return True

    def get_pinnacle_data(self):
        if not self.api_token:
            print("API token is missing.")
            return

        url_balance = f"{self.base_url}/api/transaction/balance"
        url_pinnacle = f"{self.base_url}/api/users/pinnacle"
        params = {
            "access_token": self.api_token,
            "_locale": "en",
            "_format": "json"
        }

        attempts = 999
        for attempt in range(attempts):
            try:
                response = self.session.post(url_balance, params=params)
                response.raise_for_status()

                response = self.session.post(url_pinnacle, params=params)
                response.raise_for_status()

                pinnacle_data = response.json()
                return pinnacle_data['token']
            except (requests.RequestException, KeyError) as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                if attempt < attempts - 1:
                    time.sleep(5)
                else:
                    print("Max retries reached. Exiting.")
                    return None

    def get_balance(self):
        timestamp = int(time.time() * 1000)
        url = f"{API_TENDER_88_URL}/member-service/v2/account-balance?locale=en_US&_={timestamp}&withCredentials=true"
        res = self.session.get(url)
        data = json.loads(res.text)

        if 'betCredit' in data:
            return data
        else:
            return False

    def get_auth_token(self):
        if not self.token_pinnacle:
            print("Pinnacle token is missing.")
            return

        timestamp = int(time.time() * 1000)
        url = f'{API_TENDER_88_URL}/member-service/v2/auth-token?locale=en_US&_={timestamp}&withCredentials=true'
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "ru,en;q=0.9",
            "content-type": "application/json;charset=UTF-8",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"130\", \"YaBrowser\";v=\"24.12\", \"Not?A_Brand\";v=\"99\", \"Yowser\";v=\"2.5\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-app-data": "lang=en_US"
        }

        body = {
            "token": self.token_pinnacle,
            "locale": "en",
            "oddsFormat": "HK",
            "sport": None,
            "view": None,
            "mode": None,
            "parentUrl": None
        }

        self.session.post(url, json=body, headers=headers)
