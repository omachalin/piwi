import asyncio, os, time, sys, subprocess, random, json
from auth import PiwiAuth
from config import (API_TENDER_88_URL)
from proxy import Proxy
from sender import Sender
from libs.libs import Libs
from pinnacle_api import PinnacleApi
from colorama import init, Fore

init(autoreset=True)

class Piwi247:
    events = []
    status_events_id = {}
    maxes = {}
    cookies_dict = None,
    banned_proxies = []
    sports = {
        4: 'basketball',
        12: 'esports',
        19: 'hockey',
        29: 'soccer',
        33: 'tennis',
        34: 'voleyball',
    }

    async def get_proxies(self):
        self.proxies = await Proxy.get_proxies()
        for proxy in self.proxies:
            proxy['timestamp'] = time.time()

    @classmethod
    async def set_status_event(cls, event_id, status):
        if event_id in cls.status_events_id:
            cls.status_events_id[event_id] = status


    async def get_result_market(
            self,subevent, lineId, name, coef, unavailable,
            offline, period=0, l=None, max=None, handicap=0, special_header='', line=None, id_pinnacle=None):

        shtora = 1
        if unavailable is False and offline is False:
            shtora = 0

        result = {
            'id': lineId,
            'name': name,
            'coef': coef,
            'subevent': subevent,
            'shtora': shtora,
            'period': period,
            'handicap': handicap,
        }

        if l:
            result['l'] = l
        if max:
            result['max'] = max
        if special_header != '':
            result['special_header'] = special_header
        if line:
            result['line'] = line
        if id_pinnacle:
            result['id_pinnacle'] = id_pinnacle

        return result

    async def get_maxes(self, event_id, params, markets, proxy):
        current_timestamp = int(time.time() * 1000)

        payload = {
            'oddsSelections': []
        }

        for p in params:
            odds_id = f"{p['id']}|0|99|10|0|{p['h']}|{p['i']}"
            selection_id = f"{p['l']}|{p['id']}|0|99|10|0|{p['h']}|{p['i']}|0"
            payload['oddsSelections'].append({
                'oddsFormat': 1,
                'oddsId': odds_id,
                'oddsSelectionsType': 'OUTRIGHT',
                'selectionId': selection_id
            })

        url = (
            f"{API_TENDER_88_URL}/member-service/v2/all-odds-selections?locale=en_US"
            f"&_={current_timestamp}&withCredentials=true"
        )

        try:
            maxes = await Libs.post(
                url=url,
                data=payload,
                cookies=self.cookies_dict,
                proxy=proxy,
                timeout=3
            )
        except Exception as _:
            return markets

        for special_market in markets:
            if 'l' in special_market:
                for max in maxes:
                    if max['lineId'] == special_market['l']:
                        special_market['max'] = max['maxStake']
                        key = f"{event_id}_{special_market['l']}"
                        self.maxes[key] = max['maxStake']

        return markets

    async def get_markets(self, event, proxy_number):
        event['markets'] = []
        current_timestamp = int(time.time() * 1000)
        proxy = self.proxies[proxy_number]
        data_maxes = []
        url = (
            f"{API_TENDER_88_URL}/sports-service/sv/euro/odds/event?"
            f"eventId={event['id']}&oddsType=1&version=0&specialVersion=0&locale=en_US&"
            f"_={current_timestamp}&withCredentials=true"
        )

        #print(url)

        try:
            data = await Libs.get(url, cookies=self.cookies_dict, proxy=proxy, timeout=5)
            if data == 403:
                self.banned_proxies.append(proxy)
                return False
            event['match_time'] = int(data['normal']['time'] / 1000)
        except Exception as e:
            data = {}
            self.proxies[proxy_number]['timestamp'] = int(time.time()) + 10
            await self.set_status_event(event_id=event['id'], status='free')

        for key, value in data.items():
            if value and isinstance(value, dict) and 'periods' in value and event['live']:
                for key_child, market_list in value['periods'].items():
                    subevent = f"{event['sport_name']}_{key}_{key_child}"
                    for market_key, market_detail in market_list.items():
                        if isinstance(market_detail, list):
                            for idx_detail, detail in enumerate(market_detail):
                                if 'lineId' not in detail or detail['offline'] is True:
                                    continue
                                if market_key == 'handicap':
                                    is_alt_line = '1' if detail['isAlt'] else '0'
                                    if 'homeSpread' in detail:
                                        id = f"{event['id']}|{key_child}|2|0|{is_alt_line}|{detail['homeSpread']}"
                                        handicap = detail['homeSpread'].replace('+', '')
                                        spread_home = await self.get_result_market(
                                            subevent=subevent,
                                            lineId=detail['lineId'],
                                            name=f"spread_home_{handicap}",
                                            coef=detail['homeOdds'],
                                            unavailable=detail['unavailable'],
                                            offline=detail['offline'],
                                            period=key_child,
                                            handicap=handicap,
                                            id_pinnacle=id,
                                        )

                                        spread_home['path_odds'] = (
                                            f"{key}/periods/{key_child}/{market_key}/{idx_detail}/homeOdds"
                                        )

                                        spread_home['path_line'] = (
                                            f"{key}/periods/{key_child}/{market_key}/{idx_detail}/homeSpread"
                                        )

                                        event['markets'].append(spread_home)
                                    if 'awaySpread' in detail:
                                        id = f"{event['id']}|{key_child}|2|1|{is_alt_line}|{detail['awaySpread']}"
                                        handicap = detail['awaySpread'].replace('+', '')
                                        spread_away = await self.get_result_market(
                                            subevent=subevent,
                                            lineId=detail['lineId'],
                                            name=f"spread_away_{handicap}",
                                            coef=detail['awayOdds'],
                                            unavailable=detail['unavailable'],
                                            offline=detail['offline'],
                                            period=key_child,
                                            handicap=handicap,
                                            id_pinnacle=id,
                                        )

                                        spread_away['path_odds'] = (
                                            f"{key}/periods/{key_child}/{market_key}/{idx_detail}/awayOdds"
                                        )

                                        spread_away['path_line'] = (
                                            f"{key}/periods/{key_child}/{market_key}/{idx_detail}/awaySpread"
                                        )

                                        event['markets'].append(spread_away)
                                elif market_key == 'overUnder':
                                    is_alt_line = '1' if detail['isAlt'] else '0'
                                    handicap = detail['points'].replace('+', '')

                                    id_home = f"{event['id']}|{key_child}|3|3|{is_alt_line}|{detail['points']}"
                                    id_away = f"{event['id']}|{key_child}|3|4|{is_alt_line}|{detail['points']}"

                                    home = await self.get_result_market(
                                        subevent=subevent,
                                        lineId=detail['lineId'],
                                        name=f"total_over_{handicap}",
                                        coef=detail['overOdds'],
                                        unavailable=detail['unavailable'],
                                        offline=detail['offline'],
                                        period=key_child,
                                        handicap=handicap,
                                        id_pinnacle=id_home,
                                    )

                                    home['path_odds'] = f"{key}/periods/{key_child}/{market_key}/{idx_detail}/overOdds"
                                    home['path_line'] = f"{key}/periods/{key_child}/{market_key}/{idx_detail}/points"

                                    away = await self.get_result_market(
                                        subevent=subevent,
                                        lineId=detail['lineId'],
                                        name=f"total_under_{handicap}",
                                        coef=detail['underOdds'],
                                        unavailable=detail['unavailable'],
                                        offline=detail['offline'],
                                        period=key_child,
                                        handicap=handicap,
                                        id_pinnacle=id_away,
                                    )

                                    away['path_odds'] = f"{key}/periods/{key_child}/{market_key}/{idx_detail}/underOdds"
                                    away['path_line'] = f"{key}/periods/{key_child}/{market_key}/{idx_detail}/points"

                                    event['markets'].extend([home, away])
                        elif isinstance(market_detail, dict):
                            if market_key == 'teamTotals':
                                for home_or_away in ['home', 'away']:
                                    if home_or_away not in market_detail or 'points' not in market_detail[home_or_away]:
                                        continue

                                    point = market_detail[home_or_away]['points'].replace('+', '')
                                    name = (
                                        f"{home_or_away}_team_total_%%_{point}"
                                    )

                                    id_over = ''
                                    id_under = ''
                                    is_alt_line = '0'
                                    if 'isAlt' in market_detail[home_or_away]:
                                        is_alt_line = '1'

                                    point_symbols = market_detail[home_or_away]['points']

                                    if home_or_away == 'home':
                                        id_over = f"{event['id']}|{key_child}|4|5|{is_alt_line}|{point_symbols}"
                                        id_under = f"{event['id']}|{key_child}|4|6|{is_alt_line}|{point_symbols}"
                                    elif home_or_away == 'away':
                                        id_over = f"{event['id']}|{key_child}|5|7|{is_alt_line}|{point_symbols}"
                                        id_under = f"{event['id']}|{key_child}|5|8|{is_alt_line}|{point_symbols}"

                                    over = await self.get_result_market(
                                        subevent=subevent,
                                        lineId=market_detail[home_or_away]['lineId'],
                                        name=name.replace('%%', 'over'),
                                        coef=market_detail[home_or_away]['overOdds'],
                                        unavailable=market_detail[home_or_away]['unavailable'],
                                        offline=market_detail[home_or_away]['offline'],
                                        period=0,
                                        handicap=point,
                                        id_pinnacle=id_over,
                                    )

                                    over['path_odds'] = (
                                        f"{key}/periods/{key_child}/{market_key}/{idx_detail}/{home_or_away}/overOdds"
                                    )

                                    over['path_line'] = (
                                        f"{key}/periods/{key_child}/{market_key}/{idx_detail}/{home_or_away}/points"
                                    )

                                    under = await self.get_result_market(
                                        subevent=subevent,
                                        lineId=market_detail[home_or_away]['lineId'],
                                        name=name.replace('%%', 'under'),
                                        coef=market_detail[home_or_away]['underOdds'],
                                        unavailable=market_detail[home_or_away]['unavailable'],
                                        offline=market_detail[home_or_away]['offline'],
                                        period=0,
                                        handicap=point,
                                        id_pinnacle=id_under,
                                    )

                                    under['path_odds'] = (
                                        f"{key}/periods/{key_child}/{market_key}/{idx_detail}/{home_or_away}/underOdds"
                                    )

                                    under['path_line'] = (
                                        f"{key}/periods/{key_child}/{market_key}/{idx_detail}/{home_or_away}/points"
                                    )

                                    event['markets'].extend([over, under])

                            elif market_key == 'moneyLine':
                                if 'lineId' in market_detail:
                                    for match in ['homePrice', 'awayPrice', 'drawPrice']:
                                        if match not in market_detail:
                                            continue

                                        id_pinnacle = f"{event['id']}|{key_child}|1"

                                        name = ''
                                        if match == 'homePrice':
                                            name = 'match_1'
                                            id_pinnacle += '|0|0|0'
                                        elif match == 'awayPrice':
                                            name = 'match_2'
                                            id_pinnacle += '|1|0|0'
                                        elif match == 'drawPrice':
                                            name = 'match_x'
                                            id_pinnacle += '|2|0|0'
                                        if market_detail[match] == '':
                                            market_detail[match] = 0

                                        res_m = await self.get_result_market(
                                            subevent=subevent,
                                            lineId=market_detail['lineId'],
                                            name=name,
                                            coef=market_detail[match],
                                            unavailable=market_detail['unavailable'],
                                            offline=market_detail['offline'],
                                            period=key_child,
                                            id_pinnacle=id_pinnacle,
                                        )


                                        res_m['path_odds'] = (
                                            f"{key}/periods/{key_child}/{market_key}/{idx_detail}/{match}"
                                        )

                                        res_m['path_line'] = ''

                                        res_m['handicap'] = ''

                                        event['markets'].append(res_m)
            elif value and isinstance(value, list) and key == 'specials':
                subevent = f"{event['sport_name']}_specials"
                for special_list_idx, special_list in enumerate(value):
                    for special_idx, special in enumerate(special_list['events']):
                        name = special['name']
                        for contestant_idx, contestant in enumerate(special['contestants']):
                            name = special['name']
                            team_home_underline = event['team_home'].replace(' ', '_')
                            team_away_underline = event['team_home'].replace(' ', '_')
                            name = name.replace(team_home_underline, 'Home').replace(team_away_underline, 'Away')
                            key_max = f"{event['id']}_{contestant['l']}"
                            max = self.maxes.get(key_max, None)
                            id = f"{event['id']}|0|99|10|0|{contestant['i']}"

                            special = await self.get_result_market(
                                subevent=subevent,
                                lineId=special['id'],
                                name=name,
                                coef=contestant['p'],
                                line=contestant['h'],
                                unavailable=False,
                                offline=False,
                                l=contestant['l'],
                                max=max,
                                special_header=special_list['code'],
                                id_pinnacle=id,
                            )

                            special['path_odds'] = (
                                f"specials/{special_list_idx}/events/{special_idx}/contestants/{contestant_idx}/p"
                            )

                            special['path_line'] = ''

                            special['name_over_under'] = f"{name}_{contestant['n']}_{contestant['h']}".lower()

                            event['markets'].append(special)

                            if event['live'] is False and max is None:
                                data_maxes.append({
                                    'id': special['id'],
                                    'h': 0 if contestant['h'] is None else contestant['h'],
                                    'i': contestant['i'],
                                    'l': contestant['l'],
                                })

                                if len(data_maxes) == 9:
                                    event['markets'] = await self.get_maxes(
                                        event_id=event['id'],
                                        params=data_maxes,
                                        markets=event['markets'],
                                        proxy=self.proxies[random.randint(0, 99)],
                                    )

                                    data_maxes = []

        if data_maxes:
            event['markets'] = await self.get_maxes(
                event_id=event['id'],
                params=data_maxes,
                markets=event['markets'],
                proxy=self.proxies[random.randint(0, 99)]
            )

        if event['markets']:
            sender = Sender()

            try:
                pinnacle_api_obj = PinnacleApi()
                if event['live'] is True:
                    event['score'] = await pinnacle_api_obj.get_score(event_id=event['id'], sport_id=event['game_id'])
            except Exception as e:
                await self.set_status_event(event_id=event['id'], status='free')

            await sender.prepare_data(
                event=event,
                callback=lambda: self.set_status_event(event_id=event['id'], status='free'),
            )
        else:
            # self.events.remove(event)
            self.status_events_id.pop(event['id'])


    async def set_events(self, url, sport_name, sport_id, live):
        if not self.cookies_dict:
            return False

        data = await Libs.get(
            url,
            cookies=self.cookies_dict,
            #proxy=self.proxies[random.randint(0, len(self.proxies) - 1)]
        )

        existing_event_ids = {event['id'] for event in self.events}
        if data is None or 'leagues' not in data:
            return None

        for league in data['leagues']:
            for event in league['events']:
                if int(event['id']) in existing_event_ids:
                    continue
                self.events.append({
                    'id': event['id'],
                    'league_id': league['id'],
                    'sport_name': sport_name,
                    'game_id': sport_id,
                    'team_home': event['participants'][0]['englishName'],
                    'team_away': event['participants'][1]['englishName'],
                    'score': '0:0',
                    'markets': [],
                    'live': live
                })

    async def get_basketball_offline_events(self):
        current_timestamp = int(time.time() * 1000)

        url = (
            f"{API_TENDER_88_URL}/sports-service/sv/euro/odds/league?sportId=4&oddsType=1"
            f"&version=0&timeStamp={current_timestamp}&periodNum=-1&eSportCode=&locale=en_US"
            f"&leagueCode=nba&isHlE=true&isLive=false&eventType=0&_={current_timestamp}&withCredentials=true"
        )

        await self.set_events(
            url=url,
            sport_name='basketball',
            sport_id=4,
            live=False
        )

    async def noop(self):
        pass

    async def get_football_specials(self):
        current_timestamp = int(time.time() * 1000)

        url = (
            f"{API_TENDER_88_URL}/sports-service/sv/compact/outright?oddSince=0&fixtureSince=0&ot=2"
            f"&g=QQ==&ort=2&_g=0&mk=3&sportId=29&_={current_timestamp}&locale=en_US"
        )

        data = await Libs.get(
            url,
            cookies=self.cookies_dict
        )

        if data is None or 'a' not in data:
            return False

        events = []

        for item in data['a']:
            for se in item['se']:
                if se['n'] == 'Both Teams To Score?':
                    teams = se['e'].split(' vs ')
                    events.append({
                        'id': se['ei'],
                        'league_id': item['li'],
                        'sport_name': 'soccer',
                        'game_id': 29,
                        'team_home': teams[0].lower(),
                        'team_away': teams[1].lower(),
                        'score': '0:0',
                        'markets': [],
                        'match_time': 0,
                        'live': False
                    })

                    for market in se['l']:
                        events[-1]['markets'].append({
                            'id': market['i'],
                            'name': f"{se['n']}_{market['n']}".lower(),
                            'coef': market['p'],
                            'subevent': 'soccer_specials',
                            'shtora': 0,
                            'period': 0,
                            'handicap': 0,
                            'id_pinnacle': 0,
                            'path_odds': 0,
                            'path_line': 0,
                        })

        sender = Sender()
        for event in events:
            asyncio.create_task(sender.prepare_data(event=event, callback=self.noop))

    async def get_events(self):
        for sport_id, sport_name in self.sports.items():
            current_timestamp = int(time.time() * 1000)

            url = (
                f"{API_TENDER_88_URL}/sports-service/sv/euro/odds?"
                f"sportId={sport_id}&isLive=true&isHlE=false&oddsType=1&version=0"
                f"&timeStamp={current_timestamp}&language=en&isHomePage=&leagueCode="
                "&eventType=0&eSportCode=&periodNum=-1&participant=&locale=en_US"
                f"&_={current_timestamp}&withCredentials=true"
            )

            await self.set_events(
                url=url,
                sport_name=sport_name,
                sport_id=sport_id,
                live=True
            )

            await asyncio.sleep(3)
            print(Fore.YELLOW + f"Получили события ({sport_name})")
            print(Fore.YELLOW + f"Длина событий: {len(self.events)}")

    async def count_active_connections(self, print_flag=False):
        active_connections = subprocess.check_output(
            "ss -an | grep ':1080 ' | grep ESTAB | wc -l", shell=True, universal_newlines=True
        )
        if active_connections:
            count_fetches = int(active_connections.strip())
            if print_flag:
                print('Active fetches: ', count_fetches)
            return count_fetches
        return 0

    async def restart_script(self, interval_hours=1):
        while True:
            await asyncio.sleep(interval_hours * 3600)
            print(f"Перезагрузка скрипта через {interval_hours} часов...")
            os.execv(sys.executable, [sys.executable] + sys.argv)

    async def periodic_get_proxies(self):
        while True:
            await asyncio.sleep(60)
            await self.get_proxies()

    async def periodic_get_events(self):
        while True:
            await asyncio.sleep(60)
            await self.get_football_specials()
            await self.get_basketball_offline_events()
            await self.get_events()

    async def periodic_check_auth(self):
        obj_auth = PiwiAuth()
        self.update_cookies(obj_auth)

        while True:
            await asyncio.sleep(20)
            if not obj_auth.get_balance():
                print("Обновление сессии...")
                obj_auth = PiwiAuth()
                self.update_cookies(obj_auth)

    def update_cookies(self, obj_auth):
        session = obj_auth.get_session()
        if session is not None:
            self.cookies_dict = {cookie.name: cookie.value for cookie in session.cookies}

    async def run(self):
        asyncio.create_task(self.periodic_check_auth())
        await Sender.get_config()
        await self.get_proxies()
        await self.get_football_specials()
        await self.get_basketball_offline_events()
        await self.get_events()

        asyncio.create_task(self.periodic_get_events())
        #asyncio.create_task(self.periodic_get_proxies())
        asyncio.create_task(Sender.clear_sended_data_periodically())
        asyncio.create_task(Sender.periodic_update_config())
        asyncio.create_task(self.restart_script())

        proxy_number = 0

        while True:
            # Удаляем забаненные прокси
            for proxy in self.banned_proxies:
                if proxy in self.proxies:
                    self.proxies.remove(proxy)
            self.banned_proxies.clear()

            if not self.proxies:
                print("Нет доступных прокси, жду 10 секунд...")
                await asyncio.sleep(10)
                continue

            proxy_lenght = len(self.proxies)
            proxy_number = proxy_number % proxy_lenght

            print(Fore.YELLOW +
                f"Длина событий: {len(self.events)} "
                f"Количество максов: {len(self.maxes)} "
                f"Валидные прокси: {proxy_lenght}"
            )

            random.shuffle(self.events)

            for event in self.events:
                current_timestamp = time.time()
                if event['id'] in self.status_events_id and self.status_events_id[event['id']] == 'busy':
                    continue

                suitable_proxy_found = False

                for _ in range(proxy_lenght):
                    if current_timestamp - self.proxies[proxy_number]['timestamp'] >= 2.5:
                        suitable_proxy_found = True
                        break
                    proxy_number = (proxy_number + 1) % proxy_lenght

                if not suitable_proxy_found:
                    continue

                self.status_events_id[event['id']] = 'busy'

                asyncio.create_task(self.get_markets(event=event, proxy_number=proxy_number))

                self.proxies[proxy_number]['timestamp'] = current_timestamp
                proxy_number = (proxy_number + 1) % proxy_lenght

            await asyncio.sleep(4)

async def main():
    piwi = Piwi247()
    await piwi.run()

asyncio.run(main())
