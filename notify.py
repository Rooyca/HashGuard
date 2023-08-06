import apprise, os

apobj = apprise.Apprise()
config = apprise.AppriseConfig()
config.add(os.getenv("CONFIG_APPRISE", './config.yml'))
apobj.add(config)