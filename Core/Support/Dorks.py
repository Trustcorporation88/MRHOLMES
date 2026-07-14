# ORIGINAL CREATOR: Luca Garofalo (Lucksi)
# AUTHOR: Luca Garofalo (Lucksi)
# Copyright (C) 2021-2023 Lucksi <lukege287@gmail.com>
# License: GNU General Public License v3.0

from Core.Support import Font
from Core.Support import Language
from time import sleep

filename = Language.Translation.Get_Language()
filename


class Search:

    @staticmethod
    def dork(username, report, nomefile, Type, compact=False):
        print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE +
              Language.Translation.Translate_Language(filename, "Dorks", "Generation", "None").format(Type))
        sleep(1)
        username = username.replace(" ","+")
        f = open(report, "a")
        f.write(Type + "-DORKS:\n\n")
        f.close()
        sleep(1)
        f = open(nomefile, "r")
        
        shown = 0
        total = 0
        for sites in f:
            site = sites.rstrip("\n")
            site = site.replace("{}", username)
            total += 1
            
            fr = open(report, "a")
            fr.write(site + "\n")
            fr.close()
            
            if compact:
                is_social = any(s in site.lower() for s in ["instagram", "facebook", "linkedin", "twitter", "vk.com"])
                is_general = not any(ext in site.lower() for ext in ["filetype:", "mime:"])
                
                if is_social or (is_general and shown < 2):
                    print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + site)
                    shown += 1
            else:
                print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + site)
        
        f.close()
        
        if compact and total > shown:
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + f"... +{total - shown} dorks salvos no arquivo")
        
        print(Font.Color.WHITE + Language.Translation.Translate_Language(filename,
              "Default", "Report", "None") + report)

    @staticmethod
    def Generator(Type,nomefile,report,phrase,exclusion,data,between,seconddata):
        print(Font.Color.GREEN + "\n[+]" + Font.Color.WHITE +
              Language.Translation.Translate_Language(filename, "Dorks", "Generation", "None").format(Type))
        sleep(2)
        if Type == "YANDEX":
            if "before:" in data:
                data = data.replace("+before:","date:<")
            elif "after" in data:
                data = data.replace("+after:","date:>")
            if between == "True":
                seconddata = seconddata.replace("before","")
                seconddata = seconddata.replace("+after","")
                data = "date:"+ seconddata
            else:
                pass
            data = data.replace("/","")
        phrase = phrase.replace(" ","+")
        f = open(report, "a")
        f.write("\n" + Type + "-DORKS:\n\n")
        f.close()
        sleep(3)
        f = open(nomefile, "r")
        for sites in f:
            site = sites.rstrip("\n")
            if exclusion and data == "None":
                site = site.replace("{}", phrase)
            else:
                site = site.replace("{}", phrase).replace(")","){}".format(data) + "".join(exclusion))
            print(Font.Color.YELLOW + "[v]" + Font.Color.WHITE + site)
            f = open(report, "a")
            f.write(site + "\n")
        f.close()
        f.close()
        print(Font.Color.WHITE + Language.Translation.Translate_Language(filename,
              "Default", "Report", "None") + report)

