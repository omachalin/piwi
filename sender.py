import json, asyncio
from libs.libs import Libs
from urllib.parse import urlencode
from time import gmtime, strftime
from datetime import datetime


class Sender:
    MAIN_SERVER = 'http://167.235.13.54:1043'
    BROKER_ID = 3
    DATA_BROKER_ID = 26
    config = []
    event_name_id = '1389'
    sended_data = {
        'team_mapping': {},
        'sport_mapping': {},
        'game': {},
        'gameday': {},
        'market_mapping': {},
        'sub_game_mapping': {}
    }

    type_market = {
        'TEAM_TOTAL_POINTS': ['team_total'],
        'MONEYLINE': ['match_1', 'match_2', 'match_x'],
        'TOTAL_POINTS': ['total'],
        'SPREAD': ['spread'],
    }

    clear_thread_sended_data = False
    update_config_process = False

    @classmethod
    async def clear_sended_data_periodically(cls):
        while True:
            await asyncio.sleep(600)
            cls.clear_thread_sended_data = True
            print('Очищаем sended_data...')
            cls.sended_data = {
                'team_mapping': {},
                'sport_mapping': {},
                'game': {},
                'gameday': {},
                'market_mapping': {},
                'sub_game_mapping': {}
            }

            cls.clear_thread_sended_data = False

    async def get_etalon_id(self, team_home_id, team_away_id):
        team_home_id = int(team_home_id)
        team_away_id = int(team_away_id)
        min_num = min(team_home_id, team_away_id)
        max_num = max(team_home_id, team_away_id)

        return f"{min_num},{max_num}"

    async def get_game_day_id(self, game_id, order_team, order_team_etalon):
        if (game_id in self.config['gameday'] and self.config['gameday'][game_id].get('pinnacle') != '-'):
            return True

        if (game_id in self.sended_data['gameday']):
            return False

        self.sended_data['gameday'][game_id] = 1

        params = {
            'table_name': 'game_day',
            'game_id': game_id,
            'broker_id': self.BROKER_ID,
            'field': 'pinnacle',
            'etalon_team_id': order_team_etalon,
            'team_id': order_team,
        }

        query_string = urlencode(params)
        url = f"{self.MAIN_SERVER}/adddata?{query_string}"
        await Libs.get(url=url)
        self.config['gameday'][game_id] = {'pinnacle': True}

    async def get_game_id(self, order_team, order_team_etalon, sport_id):
        if order_team_etalon in self.config['game'][sport_id][self.event_name_id]:
            return self.config['game'][sport_id][self.event_name_id][order_team_etalon]
        else:
            if order_team_etalon in self.sended_data['game']:
                return False
            self.sended_data['game'][order_team_etalon] = 1

            try:
                params = {
                    'table_name': 'game',
                    'broker_id': self.BROKER_ID,
                    'sport_id': sport_id,
                    'event_name_id': self.event_name_id,
                    'etalon_team_id': order_team_etalon,
                    'team_id': order_team,
                }

                query_string = urlencode(params)
                url = f"{self.MAIN_SERVER}/adddata?{query_string}"
                response = await Libs.get(url=url)

                id = response['data']['game'][sport_id][self.event_name_id][order_team_etalon]
                self.config['game'][sport_id][self.event_name_id][order_team_etalon] = id
                return id
            except Exception as e:
                print(f"Ошибка при создании game_id {order_team} {order_team_etalon}: {e}")
                return None

    async def get_id_mapping(self, table_name, value):
        value = value.lower()
        value = value.replace("'", '')
        value = value.replace("+", '')
        value = value.replace("/", '')
        value = value.replace("&", '')
        try:
            if table_name not in self.sended_data:
                self.sended_data[table_name] = {}
            if table_name not in self.config:
                self.config[table_name] = {}

            if not value in self.config[table_name] and value not in self.sended_data[table_name]:
                self.sended_data[table_name][value] = 1
                url = f"{self.MAIN_SERVER}/adddata?table_name={table_name}&broker_id={self.BROKER_ID}&name={value}"
                response = await Libs.get(url=url)
                if response['data'][table_name][value]:
                    self.config[table_name][value] = response['data'][table_name][value]
                    return self.config[table_name][value]
            else:
                if value in self.config[table_name]:
                    return self.config[table_name][value]
        except Exception as e:
            self.sended_data[table_name][value] = 1
            if 'market_mapping_vilka' not in table_name:
                print(f"Ошибка при получении id mapping {table_name} {value}: {e}")

    async def get_type_bet(self, market_name):
        find_market = False
        bet_type = ''

        for type_market in self.type_market:
            for value in self.type_market[type_market]:
                if value in market_name:
                    bet_type = type_market
                    find_market = True
                    break
            if find_market:
                break
        return bet_type

    async def prepare_data(self, event, callback):
        if self.clear_thread_sended_data or self.update_config_process:
            await callback()
            return False

        team_home = event['team_home']
        team_away = event['team_away']
        score = event['score']
        markets = event['markets']
        sport_name = event['sport_name']
        match_time = event['match_time']
        event_id = event['id']
        sport_id_pinnacle = event['game_id']
        league_id = event['league_id']
        date_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        results = []

        team_home_id = await self.get_id_mapping(table_name='team_mapping', value=team_home)
        team_away_id = await self.get_id_mapping(table_name='team_mapping', value=team_away)

        if not team_home_id or not team_away_id:
            await callback()
            return False
        sport_id = await self.get_id_mapping(table_name='sport_mapping', value=sport_name)

        order_team = f"{team_home_id},{team_away_id}"
        order_team_etalon = await self.get_etalon_id(team_home_id=team_home_id, team_away_id=team_away_id)

        if not order_team_etalon:
            print('Не удалось получить order_team_etalon')
            await callback()
            return False

        game_id = await self.get_game_id(
            order_team=order_team,
            order_team_etalon=order_team_etalon,
            sport_id=sport_id,
        )

        if not game_id:
            await callback()
            return False

        await self.get_game_day_id(
            game_id=game_id,
            order_team=order_team,
            order_team_etalon=order_team_etalon
        )

        match_title = team_home + ' - ' + team_away
        url = f"{self.MAIN_SERVER}/adddatajsonparsing"

        vilka_obj = {}

        for market in markets:
            market_id = await self.get_id_mapping(
                table_name='market_mapping',
                value=market['name']
            )

            if market_id is False:
                continue

            if market['subevent'] not in vilka_obj:
                vilka_obj[market['subevent']] = {}

            vilka_obj[market['subevent']][market_id] = market['coef']

        for market in markets:
            period_number = market['period']
            market_id = await self.get_id_mapping(
                table_name='market_mapping',
                value=market['name']
            )

            if not market_id:
                continue

            type_line_param_id = await self.get_id_mapping(
                table_name='sub_game_mapping',
                value=market['subevent']
            )

            if not type_line_param_id:
                continue

            odds = market['coef']

            bei_id = ''
            handicap = market['handicap']
            bet_type = await self.get_type_bet(
                market_name=market['name']
            )

            team = ''
            if 'away' in market['name'] or 'match_2' in market['name']:
                team = 'Team2'
            elif 'home' in market['name'] or 'match_1' in market['name']:
                team = 'Team1'

            if team == '' and bet_type == 'MONEYLINE':
                team = 'Draw'

            side = ''
            if 'over' in market['name']:
                side = 'OVER'
            elif 'under' in market['name']:
                side = 'UNDER'

            basketball_special = ''
            max = ''
            match_name = ''

            if event['live'] is False and 'max' in market:
                max = market['max']
                url = f"{self.MAIN_SERVER}/adddatajsonparsingline"
                if 'name_over_under' in market:
                    basketball_special = f"!!!{market['name']}!!!{market['name_over_under']}"
                if match_time:
                    date_time = datetime.utcfromtimestamp(event['match_time']).strftime('%Y-%m-%d %H:%M:%S')

                match_name = f"{team_home} - {team_away}"

            vilka_id = await self.get_id_mapping(
                value=market_id,
                table_name='market_mapping_vilka',
            )

            if vilka_id is False:
                continue

            if odds == 0 or odds == '':
                odds = 1

            coef_vilka = 0
            real_marge = 0.072

            if market['subevent'] in vilka_obj and vilka_id in vilka_obj[market['subevent']]:
                coef_vilka = float(vilka_obj[market['subevent']][vilka_id])
                if coef_vilka == '':
                    coef_vilka = 0
                if coef_vilka != 0 and float(odds) != 0:
                    try:
                        real_marge = round((1 / float(odds) + 1 / float(coef_vilka) - 1), 4)
                    except (ValueError, ZeroDivisionError):
                        print(f"Ошибка в строке: value - {odds}, coef_vilka - {coef_vilka}")

            real_coef = round(float(odds) * (1 + real_marge), 3)
            real_delta = 0

            if real_coef != 0:
                real_delta = round(1 / real_coef, 3)

            bei_id = (
                f"{event_id}!!!{sport_id_pinnacle}!!!{league_id}!!!{period_number}!!!"
                f"{handicap}!!!Decimal!!!{bet_type}!!!{team}!!!{side}"
                f"!!!{match_name}{basketball_special}"
            )

            id = market['id_pinnacle']

            url_str = (
                f"{market_id}___{sport_id}___{self.event_name_id}___{match_title}___{type_line_param_id}___"
                f"{team_home_id}___{team_away_id}___{score}___{match_time}___{odds}___"
                f"{game_id}___{market['shtora']}___{bei_id}___{id}___{self.DATA_BROKER_ID}___"
                f"{real_coef}___{coef_vilka}___{real_marge}___{real_delta}___{date_time}___{max}___"
                f"{market['path_odds']}___{market['path_line']}"
            )

            results.append(url_str)

        await callback()

        if results:
            asyncio.create_task(
                Libs.postData(
                    url=url,
                    data={
                        'data': json.dumps(results)
                    },
                )
            )

    @classmethod
    async def periodic_update_config(cls):
        while True:
            await asyncio.sleep(600)
            print('Запрашиваем CONFIG')
            cls.update_config_process = True
            await cls.get_config()

    @classmethod
    async def get_config(cls):
        if not cls.config or cls.update_config_process:
            url = f"{cls.MAIN_SERVER}/getfullconfig?broker_id={cls.BROKER_ID}"
            response = await Libs.get(url=url, timeout=150)
            if response:
                cls.config = response['data']
                print('Получен CONFIG')
            cls.update_config_process = False
        else:
            print('config уже существует')
