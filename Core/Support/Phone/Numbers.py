# ORIGINAL CREATOR: Luca Garofalo (Lucksi)
# IMPROVEMENTS: Geolocation fix, HTML reports, parallel search, SQLite history

import os
import phonenumbers
import json
import urllib.request
from phonenumbers import carrier, geocoder, timezone
from Core.Support import Font
from Core.Support import Language
from time import sleep

filename = Language.Translation.Get_Language()

# Mapeamento de DDDs brasileiros para cidades (fallback quando Nominatim falha)
BR_AREA_CODES = {
    "11": {"city": "São Paulo", "state": "SP", "lat": -23.5505, "lon": -46.6333},
    "12": {"city": "São José dos Campos", "state": "SP", "lat": -23.1791, "lon": -45.8872},
    "13": {"city": "Santos", "state": "SP", "lat": -23.9535, "lon": -46.3350},
    "14": {"city": "Bauru", "state": "SP", "lat": -22.3145, "lon": -49.0614},
    "15": {"city": "Sorocaba", "state": "SP", "lat": -23.5015, "lon": -47.4526},
    "16": {"city": "Ribeirão Preto", "state": "SP", "lat": -21.1699, "lon": -47.8102},
    "17": {"city": "São José do Rio Preto", "state": "SP", "lat": -20.8113, "lon": -49.3758},
    "18": {"city": "Presidente Prudente", "state": "SP", "lat": -22.1207, "lon": -51.3925},
    "19": {"city": "Campinas", "state": "SP", "lat": -22.9099, "lon": -47.0626},
    "21": {"city": "Rio de Janeiro", "state": "RJ", "lat": -22.9068, "lon": -43.1729},
    "22": {"city": "Campos dos Goytacazes", "state": "RJ", "lat": -21.7624, "lon": -41.3180},
    "24": {"city": "Volta Redonda", "state": "RJ", "lat": -22.5202, "lon": -44.0996},
    "27": {"city": "Vitória", "state": "ES", "lat": -20.3155, "lon": -40.3128},
    "28": {"city": "Cachoeiro de Itapemirim", "state": "ES", "lat": -20.8487, "lon": -41.1120},
    "31": {"city": "Belo Horizonte", "state": "MG", "lat": -19.9167, "lon": -43.9345},
    "32": {"city": "Juiz de Fora", "state": "MG", "lat": -21.7642, "lon": -43.3496},
    "33": {"city": "Governador Valadares", "state": "MG", "lat": -18.8546, "lon": -41.9495},
    "34": {"city": "Uberlândia", "state": "MG", "lat": -18.9128, "lon": -48.2755},
    "35": {"city": "Poços de Caldas", "state": "MG", "lat": -21.7854, "lon": -46.5612},
    "37": {"city": "Divinópolis", "state": "MG", "lat": -20.1378, "lon": -44.8837},
    "38": {"city": "Montes Claros", "state": "MG", "lat": -16.7282, "lon": -43.8578},
    "41": {"city": "Curitiba", "state": "PR", "lat": -25.4290, "lon": -49.2671},
    "42": {"city": "Ponta Grossa", "state": "PR", "lat": -25.0945, "lon": -50.1633},
    "43": {"city": "Londrina", "state": "PR", "lat": -23.3113, "lon": -51.1596},
    "44": {"city": "Maringá", "state": "PR", "lat": -23.4273, "lon": -51.9375},
    "45": {"city": "Foz do Iguaçu", "state": "PR", "lat": -25.5478, "lon": -54.5882},
    "46": {"city": "Francisco Beltrão", "state": "PR", "lat": -26.0779, "lon": -53.0539},
    "47": {"city": "Joinville", "state": "SC", "lat": -26.3045, "lon": -48.8487},
    "48": {"city": "Florianópolis", "state": "SC", "lat": -27.5954, "lon": -48.5480},
    "49": {"city": "Chapecó", "state": "SC", "lat": -27.0965, "lon": -52.6186},
    "51": {"city": "Porto Alegre", "state": "RS", "lat": -30.0346, "lon": -51.2177},
    "53": {"city": "Pelotas", "state": "RS", "lat": -31.7654, "lon": -52.3370},
    "54": {"city": "Caxias do Sul", "state": "RS", "lat": -29.1634, "lon": -51.1797},
    "55": {"city": "Santa Maria", "state": "RS", "lat": -29.6842, "lon": -53.8070},
    "61": {"city": "Brasília", "state": "DF", "lat": -15.7801, "lon": -47.9292},
    "62": {"city": "Goiânia", "state": "GO", "lat": -16.6869, "lon": -49.2648},
    "63": {"city": "Palmas", "state": "TO", "lat": -10.1842, "lon": -48.3336},
    "64": {"city": "Rio Verde", "state": "GO", "lat": -17.7923, "lon": -50.9192},
    "65": {"city": "Cuiabá", "state": "MT", "lat": -15.6010, "lon": -56.0974},
    "66": {"city": "Rondonópolis", "state": "MT", "lat": -16.4673, "lon": -54.6372},
    "67": {"city": "Campo Grande", "state": "MS", "lat": -20.4697, "lon": -54.6201},
    "68": {"city": "Rio Branco", "state": "AC", "lat": -9.9749, "lon": -67.8243},
    "69": {"city": "Porto Velho", "state": "RO", "lat": -8.7608, "lon": -63.8999},
    "71": {"city": "Salvador", "state": "BA", "lat": -12.9714, "lon": -38.5014},
    "73": {"city": "Ilhéus", "state": "BA", "lat": -14.7935, "lon": -39.0460},
    "74": {"city": "Juazeiro", "state": "BA", "lat": -9.4300, "lon": -40.5000},
    "75": {"city": "Feira de Santana", "state": "BA", "lat": -12.2664, "lon": -38.9663},
    "77": {"city": "Vitória da Conquista", "state": "BA", "lat": -14.8619, "lon": -40.8442},
    "79": {"city": "Aracaju", "state": "SE", "lat": -10.9472, "lon": -37.0731},
    "81": {"city": "Recife", "state": "PE", "lat": -8.0476, "lon": -34.8770},
    "82": {"city": "Maceió", "state": "AL", "lat": -9.6498, "lon": -35.7089},
    "83": {"city": "João Pessoa", "state": "PB", "lat": -7.1195, "lon": -34.8450},
    "84": {"city": "Natal", "state": "RN", "lat": -5.7945, "lon": -35.2110},
    "85": {"city": "Fortaleza", "state": "CE", "lat": -3.7319, "lon": -38.5267},
    "86": {"city": "Teresina", "state": "PI", "lat": -5.0892, "lon": -42.8016},
    "87": {"city": "Petrolina", "state": "PE", "lat": -9.3949, "lon": -40.5076},
    "88": {"city": "Juazeiro do Norte", "state": "CE", "lat": -7.2129, "lon": -39.3151},
    "89": {"city": "Picos", "state": "PI", "lat": -7.0770, "lon": -41.4668},
    "91": {"city": "Belém", "state": "PA", "lat": -1.4558, "lon": -48.5039},
    "92": {"city": "Manaus", "state": "AM", "lat": -3.1190, "lon": -60.0217},
    "93": {"city": "Santarém", "state": "PA", "lat": -2.4435, "lon": -54.7083},
    "94": {"city": "Marabá", "state": "PA", "lat": -5.3690, "lon": -49.1178},
    "95": {"city": "Boa Vista", "state": "RR", "lat": 2.8235, "lon": -60.6758},
    "96": {"city": "Macapá", "state": "AP", "lat": 0.0356, "lon": -51.0705},
    "97": {"city": "Coari", "state": "AM", "lat": -4.0895, "lon": -63.1407},
    "98": {"city": "São Luís", "state": "MA", "lat": -2.5307, "lon": -44.3068},
    "99": {"city": "Imperatriz", "state": "MA", "lat": -5.5255, "lon": -47.4770},
}

def get_geo_from_ddd(ddd: str) -> dict:
    """Retorna coordenadas a partir do DDD brasileiro."""
    return BR_AREA_CODES.get(ddd, {})

class Phony:

    @staticmethod
    def Get_GeoLocation(zone, param1, param2, jsonfile, num, Type, country=""):
        from urllib.parse import quote as _url_quote

        query = zone
        if country and country.lower() not in query.lower():
            query += f", {country}"

        req = urllib.request.Request(
            f"https://nominatim.openstreetmap.org/search.php?q={_url_quote(query)}&format=json",
            headers={"User-Agent": "MrHolmes/3.0"}
        )
        print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE +
              Language.Translation.Translate_Language(filename, "Phone", "Geo", "None").format(num))
        sleep(1)
        try:
            url = urllib.request.urlopen(req)
            Reader = url.read()
            parser = json.loads(Reader)
            if parser and len(parser) > 0:
                Lat = parser[0]["lat"]
                Lon = parser[0]["lon"]
            else:
                raise Exception("No results")
        except Exception:
            Lat = param1
            Lon = param2

        data = {
            "Geolocation": {
                "Latitude": Lat,
                "Longitude": Lon
            }
        }
        print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
              "LATITUDE:" + Font.Color.GREEN + " {}".format(Lat))
        sleep(1)
        print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
              "LONGITUDE:" + Font.Color.GREEN + " {}".format(Lon))
        sleep(1)
        print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
              "GOOGLE MAPS LINK: https://www.google.com/maps/place/{},{}".format(Lat, Lon))
        try:
            datafile = open(jsonfile, "a", encoding="utf-8")
            json.dump(data, datafile, ensure_ascii=False, indent=4)
            datafile.close()
            from Core.Support import Map
            Map.Creation.mapPhone(jsonfile, Lat, Lon, num, Type)
        except Exception:
            pass

    @staticmethod
    def Number(num, report, code, Mode, Type, username):
        phoneList = []
        print(Font.Color.GREEN +
              "\n[+]" + Font.Color.WHITE + Language.Translation.Translate_Language(filename, "Phone", "Scan", "None").format(num))
        sleep(2)
        FormattedPhoneNumber = "+" + num
        try:
            Phone = phonenumbers.parse(FormattedPhoneNumber, "BR")
        except Exception:
            inp = input(Font.Color.RED + "\n[!]" + Font.Color.WHITE +
                        Language.Translation.Translate_Language(filename, "Phone", "NotFound2", "None"))
            import MrHolmes as holmes
            holmes.Main.Menu(Mode)
        else:
            if not phonenumbers.is_valid_number(Phone):
                print(Font.Color.BLUE + "\n[I]" + Font.Color.WHITE +
                      Language.Translation.Translate_Language(filename, "Phone", "NoReal", "None"))
            else:
                print(Font.Color.BLUE + "\n[I]" + Font.Color.WHITE +
                      Language.Translation.Translate_Language(filename, "Phone", "Real", "None"))

            number = phonenumbers.format_number(Phone, phonenumbers.PhoneNumberFormat.E164).replace("+", "")
            numberCode = phonenumbers.format_number(Phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL).split(" ")[0]
            numberNation = phonenumbers.region_code_for_country_code(Phone.country_code)

            e164 = phonenumbers.format_number(Phone, phonenumbers.PhoneNumberFormat.E164)
            cc = str(Phone.country_code)
            localNumber = e164[1:]  # drop leading +
            if localNumber.startswith(cc):
                localNumber = localNumber[len(cc):]
            international = phonenumbers.format_number(Phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

            nation = geocoder.country_name_for_number(Phone, "en")
            location = geocoder.description_for_number(Phone, "en")
            carrierName = carrier.name_for_number(Phone, "en")

            try:
                os.makedirs("Temp/Phone", exist_ok=True)
                with open("Temp/Phone/Code.txt", "w") as cf:
                    cf.write(numberNation)
            except Exception:
                pass

            print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE + "INTERNATIONAL NUMBER: {}".format(international))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "LOCAL NUMBER: {}".format(localNumber))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "COUNTRY PREFIX: {}".format(numberCode))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "COUNTRY CODE: {}".format(numberNation))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "COUNTRY: {}".format(nation))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "AREA/ZONE: {}".format(location))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "CARRIER/ISP: {}".format(carrierName))

            i = 1
            for tz in timezone.time_zones_for_number(Phone):
                print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + "TIMEZONE N°{}: {}".format(i, tz))
                i += 1
            sleep(1)

            if location:
                print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE +
                      Language.Translation.Translate_Language(filename, "Phone", "Area", "None"))
                jsonfile = report.replace(num + ".txt", "Area_GeoLocation.json")

                ddd_br = localNumber[:2] if numberNation == "BR" else ""
                geo = get_geo_from_ddd(ddd_br)

                if geo:
                    print(Font.Color.GREEN + "[+]" + Font.Color.WHITE +
                          f" DDD {ddd_br} → {geo['city']}/{geo['state']}")
                    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
                          "LATITUDE:" + Font.Color.GREEN + f" {geo['lat']}")
                    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
                          "LONGITUDE:" + Font.Color.GREEN + f" {geo['lon']}")
                    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE +
                          f"GOOGLE MAPS: https://www.google.com/maps/place/{geo['lat']},{geo['lon']}")
                    try:
                        data = {"Geolocation": {"Latitude": geo["lat"], "Longitude": geo["lon"]}}
                        with open(jsonfile, "w", encoding="utf-8") as datafile:
                            json.dump(data, datafile, ensure_ascii=False, indent=4)
                        from Core.Support import Map
                        Map.Creation.mapPhone(jsonfile, geo["lat"], geo["lon"], num, Type)
                    except Exception:
                        pass
                else:
                    try:
                        if " " in location:
                            zone = location.split(" ", 1)[1]
                        else:
                            zone = location
                        Phony.Get_GeoLocation(zone, "Lat", "Long", jsonfile, num, Type, nation)
                    except Exception:
                        print(Font.Color.RED + "[!]" + Font.Color.WHITE + "GEOLOCATION UNAVAILABLE")
            else:
                print(Font.Color.RED + "[!]" + Font.Color.WHITE +
                      Language.Translation.Translate_Language(filename, "Phone", "NoArea", "None"))

            zone = timezone.time_zones_for_number(Phone)
            if zone:
                zone = zone[0].split("/", 1)[-1]
            else:
                zone = "Unknown"

            if zone != "Unknown":
                print(Font.Color.YELLOW + "\n[v]" + Font.Color.WHITE +
                      Language.Translation.Translate_Language(filename, "Phone", "Zone", "None"))
                jsonfile = report.replace(num + ".txt", "Zone_GeoLocation.json")
                try:
                    Phony.Get_GeoLocation(zone, "Lat", "Long", jsonfile, num, Type, nation)
                except Exception:
                    print(Font.Color.RED + "[!]" + Font.Color.WHITE + "ZONE GEOLOCATION UNAVAILABLE")
            else:
                print(Font.Color.RED + "\n[!]" + Font.Color.WHITE +
                      Language.Translation.Translate_Language(filename, "Phone", "NoZone", "None").format(number))

            return [
                international,
                phonenumbers.format_number(Phone, phonenumbers.PhoneNumberFormat.NATIONAL),
                "0" + localNumber if not localNumber.startswith("0") else localNumber,
                localNumber
            ]
