# am2p
azure metrics to prometheus


set up thgrough the 4 must have variables and two for defining the scope of Azure resources.


TENANT_ID

CLIENT_ID

CLIENT_SECRET

SUBSCRIPTION_ID 

PREDEFINED_RESOURCES = '' default is empty str, can be used as reqexp for resource names  

PREDEFINED_TYPES = 'site' this is default for gathering metrics just for site type of resource. 
