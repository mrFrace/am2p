from prometheus_client import Gauge, start_http_server, CollectorRegistry
import time, json, re, requests, os
from datetime import datetime
import concurrent.futures, threading

metricsDefinitionURL = ''
TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
SUBSCRIPTION_ID = os.environ["SUBSCRIPTION_ID"]
DATA_DIRECTORY = os.environ["HOME"]+"/data/"
RESOURCE = 'https://management.azure.com/'
RESOURCE_GROUP = ''
RESOURCE_NAME = ''
if "PREDEFINED_RESOURCES" in os.environ.keys():
  PREDEFINED_RESOURCES = os.environ["PREDEFINED_RESOURCES"]
else:
  PREDEFINED_RESOURCES = ''
if "PREDEFINED_TYPES" in os.environ.keys():
  PREDEFINED_TYPES = os.environ["PREDEFINED_TYPES"]
else:
  PREDEFINED_TYPES = 'site'
version_regex = re.compile('\d\d\d\d-\d\d-\d\d-?\w?\w?\w?\w?\w?\w?\w?')
http_request = re.compile('https://.*')
token = ''
CFGFILENAME = 'actualdata.json'
resourceGroups = {}
resourceGroup = {}
resources = {}
resource = {}
API_VERSION = '8008-66-66'
resourcegroups_endpoint_url = f'https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups?api-version=2020-06-01'
resources_endpoint_dummy_url = f'https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resources?api-version=2020-06-01'
#resources_endpoint_dummy_url =f'https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resources?api-version=2021-04-01
metrics_endpoint_dummy_url = f'https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.Web/sites/{RESOURCE_NAME}/metrics?api-version=2{API_VERSION}'
genDefs = {}
definitions = {}
created_defs = []

class Resource():
  def __init__(self):
    self.name = ''
    self.resourceId = ''
    self.type = ''
    self.kind = ''
    self.metrics = []
    self.tags = {}
    self.metricsURL = ''
    self.metricsDefsURL = ''
    self.resourceGroup = ''
    self.responded = {}
    self.metricsDefinitions = {}
    self.lastMetric = {}
  def get_metrics(self):
    metrics = get_azure_data(self.metricsURL,token)
    return metrics
  def generate_metrics_definitions(self):
    if len(self.metricsDefinitions)>0:
      for i in self.metricsDefinitions:
        if i['name']['value'] not in created_defs:
          print(f"added new definition for metric {i['name']['value']}")
          name = re.sub(r'[\W+]', '', i['name']['value'])
          if len(i['metricAvailabilities']) > 1:
            i['metricAvailabilities'] = [{'timeGrain': 'PT1H', 'retention': 'P93D'}]
          if not 'displayDescription' in i.keys():
             self.metricsDefinitions[i]['displayDescription'] = "not specified"
          definitions[name] = Gauge(
						name,
						i['displayDescription'],
						['resource_name', 'unit', 'time_grain', 'resource_id', 'metric'],
					)
        created_defs.append(i['name']['value'])
    return definitions      
  def fix_metrics_url(self):
    version = ''
    testurl = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{self.resourceGroup}/providers/{self.type}/{self.name}/metrics?api-version=2222-22-22"
    #print(testurl)
    try:
      message = get_azure_data_raw(testurl, token)
      #print(message)
      if message is not None:
        if message.status_code != 200:
          #print(message.json())
          versions = re.findall(version_regex, message.json()['error']['message'])
          if len(versions) > 0:
            version = versions[1]
          else:
            print(f"Error: no version gathered from dummy request on {self.name} gathering the matrics url")
    finally:
      if version != '':
        self.metricsURL = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{self.resourceGroup}/providers/{self.type}/{self.name}/metrics?api-version={version}"     
        print(f"metrics url defined as {self.metricsURL} for service {self.name}")
  def fix_definitions_url(self):
    version = ''
    testurl = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{self.resourceGroup}/providers/{self.type}/{self.name}/providers/microsoft.insights/metricDefinitions?api-version=2222-22-22"
    #print(testurl)
    try:
      message = get_azure_data_raw(testurl, token)
      print(message)
      if message is not None:
        print(f" test url is {testurl}")
        if message.status_code != 200:
          #print(message.json())
          versions = re.findall(version_regex, message.json()['error']['message'])
          if len(versions) > 0:
            version = versions[1]
          else:
            print(f"Error: no version gathered from dummy request on {self.name} gathering the matrics url")
    finally:
      if version != '':
        self.metricsDefsURL = f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{self.resourceGroup}/providers/{self.type}/{self.name}/providers/microsoft.insights/metricDefinitions?api-version={version}"     
        print(f"metrics definitions url defined as {self.metricsDefsURL} for resource {self.name}")
      else:
        print(f"resource metric description url is empty ")
  def get_metrics(self):
    self.lastMetric = get_azure_data_raw(self.metricsURL, token)
    if self.lastMetric is not None: 
      if self.lastMetric.status_code != 200:
        print(self.lastMetric.status_code)
      else:
        self.lastMetric = self.lastMetric.json().get("value", [])
        for i in self.lastMetric:
          name = re.sub(r'\W+', '', i['name']['value'])
          print(name)
          for metric_value in i['metricValues']:
            for m in metric_value.keys():
              if m == 'timestamp':
                timestamp = metric_value[m]
              elif m == 'properties':
                metric_value[m]=0#print("empty mertic")
              else:
                metr = float(metric_value[m])
                definitions[name].labels(
        	    	  resource_name=self.name,
                  unit=i['unit'],
                  time_grain=i['timeGrain'],
                  resource_id=self.resourceId,
                  metric=m
                ).set(metr)

def get_token():
  token_url = f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/token'
  token_data = {
    'grant_type': 'client_credentials',
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'resource': RESOURCE
  }
  token_r = requests.post(token_url, data=token_data)
  return token_r.json().get("access_token")

def get_azure_data(req_url, token):
  headers = {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  }
  endpoint_url = req_url
  if re.findall(http_request, endpoint_url):
    response = requests.get(endpoint_url, headers=headers)
    if response.status_code == 200:
    	return response.json().get("value", [])
    else:
      print(f"request to {endpoint_url} ended up with response code {response.status_code}")
  else:
      print(f"request to {endpoint_url} is not an url")
    
def get_azure_data_raw(req_url, token):
  headers = {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  }
  endpoint_url = req_url
  if re.findall(http_request, endpoint_url):
    response = requests.get(endpoint_url, headers=headers)
    return response
  else:
      print(f"request to {endpoint_url} is not an url")
### start 

if __name__ == '__main__':
  token = get_token()
  resourceGroups = get_azure_data(resourcegroups_endpoint_url, token)
  resources = get_azure_data(resources_endpoint_dummy_url, token)
  #for i in range(0, len(resources)-1):#
  for i in range(0, 40):
    if PREDEFINED_RESOURCES != '':
      if resources[i]['name'] in PREDEFINED_RESOURCES:
        name = resources[i]['name']
        print(resources[i]['name'])
        #exit(5)
        resource[name] = Resource()
        resource[name].name = resources[i]['name']
        resource[name].resourceId = resources[i]['id']
        if 'tags' in resources[i].keys():
          resource[name].tags = resources[i]['tags']
        if 'kind' in resources[i].keys():
          resource[name].kind = resources[i]['kind']
        resource[name].type = resources[i]['type']
        resource[name].resourceGroup = resources[i]['id'].split("/")[4]
        resource[name].fix_definitions_url()
        resource[name].fix_metrics_url()
        #print(resource[resources[i]['name']].resourceGroup)
				# #resource[name].fix_definitions_url()
        url = resource[name].metricsDefsURL
        print(url)
        resource[name].metricsDefinitions = get_azure_data(url, token)
        url = resource[name].metricsUR
        print(f"{url} toto je url k metrikam")
        resource[name].lastMetrics = get_azure_data(url, token)
    elif PREDEFINED_TYPES != '':
      searching = re.compile(PREDEFINED_TYPES)
      if re.findall(searching, resources[i]['type']):
        name = resources[i]['name']
        print(resources[i]['name'])
        print(resources[i]['type'])
        #exit(6)
        resource[name] = Resource()
        resource[name].name = resources[i]['name']
        resource[name].resourceId = resources[i]['id']
        if 'tags' in resources[i].keys():
          resource[name].tags = resources[i]['tags']
        if 'kind' in resources[i].keys():
          resource[name].kind = resources[i]['kind']
        resource[name].type = resources[i]['type']
        resource[name].resourceGroup = resources[i]['id'].split("/")[4]
        resource[name].fix_definitions_url()
        resource[name].fix_metrics_url()
        #print(resource[resources[i]['name']].resourceGroup)
        #resource[name].fix_definitions_url()
        url = resource[name].metricsDefsURL
        print(url)
        resource[name].metricsDefinitions = get_azure_data(url, token)
        url = resource[name].metricsURL
        print(f"{url} toto je url k metrikam")
        resource[name].lastMetrics = get_azure_data(url, token)
      
  for res in resource.keys():
    print(res)
    print(resource[res].metricsDefinitions)
    definitions[res] = resource[res].generate_metrics_definitions()
    if len(resource[res].metricsDefinitions) < 1:
      print(f"error resource metric definition is {resource[res].metricsDefinitions}")
  print(len(resource))
  start_http_server(8000)
  while True:
    token = get_token()
    for res in resource.keys():
      print(resource[res].metricsURL)
      resource[res].get_metrics()
    time.sleep(60)

  
  



#  for i in resource:
#    print(resource[i].name, resource[i].resourceId)
