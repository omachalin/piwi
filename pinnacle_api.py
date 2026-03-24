import json, time, httpx
from config import (MAIN_SERVER_URL, PINNACLE_URL)
from libs.libs import Libs

class PinnacleApi:
    token = None
    last_get_token_time = 0

    def __init__(self):
        timestamp = time.time()
        if timestamp - PinnacleApi.last_get_token_time > 60:
            PinnacleApi.token = self.get_session_pinnacle()
            PinnacleApi.last_get_token_time = timestamp

    def get_session_pinnacle(self):
       while True:
            try:
                response = httpx.get(f"{MAIN_SERVER_URL}/getpinnjsonsettings?code=pinnacle_token")
                if response.status_code == 200:
                    token = json.loads(response.text)['data']
                    return token
                else:
                    print(f"Received status code {response.status_code}. Retrying in 5 seconds...")
                    time.sleep(5)
            except Exception as e:
                print(f"Exception occurred: {e}. Retrying in 5 seconds...")
                time.sleep(5)

    async def get_match(self, event_id):
        url=f"{PINNACLE_URL}matchups/{event_id}/related"
        headers = {
            'X-Session': PinnacleApi.token,
            'X-Api-Key': 'CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R',
        }

        response = await Libs.get(url=url, headers=headers)
        return response

    async def get_score(self, event_id, sport_id):
        match = await self.get_match(event_id=event_id)
        match = match[0]
        score = '0:0'

        try:
            if 'state' in match['participants'][0]:
                score = ''
                team_1 = match['participants'][0]['state']
                team_2 = match['participants'][1]['state']
                if sport_id == 4:  # basketball
                    if (
                        'scoreByQuarter' in team_1 and team_1['scoreByQuarter'] is not None
                        and team_2['scoreByQuarter'] is not None):
                        for i, _ in enumerate(team_1['scoreByQuarter']):
                            if i != 4:
                                score += f"Q{(i + 1)}_{team_1['scoreByQuarter'][i]}:{team_2['scoreByQuarter'][i]},"
                        score += f"{team_1['score']}:{team_2['score']}"
                elif sport_id == 29:  # soccer
                    period = ''
                    if match['participants'][0]['stats'][0]['period'] == 1:
                        period = 'P2_'
                    score += f"{period}{team_1['score']}:{team_2['score']}"
                    score += f"__CORNERS_{team_1['corners']}:{team_2['corners']}"
                elif sport_id == 33 and 'gamesBySet' in team_1 and team_1['gamesBySet'] is not None:  # tennis
                    for i, _ in enumerate(team_1['gamesBySet']):
                        score += f"{team_1['gamesBySet'][i]}:{team_2['gamesBySet'][i]},"
                        if (
                            (team_1['gamesBySet'][i] != 6 and team_2['gamesBySet'][i] != 6) or
                            (team_1['gamesBySet'][i] == 6 and team_2['gamesBySet'][i] == 6)
                        ):
                            break
                    score += f"{team_1['points']}:{team_2['points']}"
        except Exception as e:
            score = '0:0'

        return score


# async def main():
#     obj = PinnacleApi()
#     match = await obj.get_match(event_id=1602666698)
#     print(await obj.get_score(match=match[0], sport_id=29))


# if __name__ == "__main__":
#     asyncio.run(main())
