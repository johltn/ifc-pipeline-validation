import requests
import json
import pprint
import ifcopenshell
# from ifcopenshell.mvd import mvd
import ifcopenshell.util.element
import itertools
import sys
import os 
import time
import numpy as np
from Levenshtein import distance
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

base_url = "https://bs-dd-api-prototype.azurewebsites.net/api/"

def pack_classification(classification_props):
    return classification_props['propertySet'], classification_props['name'], classification_props['dataType'], classification_props['predefinedValue']

def pack_mvd(mvd_output):
    return list(mvd_output.values())[0], list(mvd_output.values())[1], list(mvd_output.values())[3].wrappedValue

def get_domain_fuzzy(domains, domain_ref, tolerance=50):
    #todo: check for case also
    idx = 0
    for i in range(len(domains)):
        #todo: Handle no match at all case
        #print(domains[i]['name'],fuzz.partial_ratio(domains[idx]['name'], domain_ref) ,fuzz.partial_ratio(domains[i]['name'], domain_ref) )
        if fuzz.partial_ratio(domains[i]['name'], domain_ref) > fuzz.partial_ratio(domains[idx]['name'], domain_ref):
            idx = i
    if fuzz.partial_ratio(domains[idx]['name'], domain_ref) > tolerance:
        return domains[idx]
    else:
        return 'The domain has not been found in the bSDD.'

def get_domains():
    url = "https://bs-dd-api-prototype.azurewebsites.net/api/Domain/v2"
    r = requests.get(url)
    return json.loads(r.text) 


def get_classifications(domain_uri):
    return json.loads(requests.get(base_url + "SearchListOpen/v2/", params={'DomainNamespaceUri': domain_uri}).text)
    

def get_classification(domain_ref, item_ref):
    domain_found = 0
    classification = 0
    for domain in get_domains():
        if domain['name'] == domain_ref:
            domain_uri = domain['namespaceUri']
            params = {'DomainNamespaceUri': domain_uri}
            list_of_classifications = json.loads(requests.get(base_url + "SearchListOpen/v2/", params=params).text)

            if list_of_classifications["numberOfClassificationsFound"] > 0:
                found_ref = 0
                for c in list_of_classifications['domains'][0]['classifications']:
                    # example_classification = [0]
                    ref = c['namespaceUri'].split("/")[-1]
                
                    if ref == item_ref:
                        found_ref = 1
                        return c
                    # else:
                    #     print('errr', ref, '  ', item_ref)
                    
                if found_ref == 0:
                    #print('No classification matched with the reference code provided' , '(',item_ref,')')
                    return 'No classification matched with the reference code provided.'

            else:
                #print('No classification found for the domain ', domain_ref)
                return 'No classification found for this domain.'
        
    if domain_found == 0:
        print(domain_ref)
        print("The domain", domain_ref,"has not been found in the bSDD.")
        return 'This domain has not been found in the bSDD.'
   
def get_classification_object(uri):
    url = "https://bs-dd-api-prototype.azurewebsites.net/api/Classification/v2"
    base_url = "https://bs-dd-api-prototype.azurewebsites.net/api/"

    r = requests.get(url, {'namespaceUri':uri})
    return json.loads(r.text) 


def control_values(requirements, data):
    print(data)
    print(requirements)



def validate_consistency(ifc_file):
    rel_associate_classifications = ifc_file.by_type("IfcRelAssociatesClassification")
    log_to_construct = {}

    prog = 0

    n = len(rel_associate_classifications)

    if n:
        rnd_array = np.random.multinomial(100, np.ones(n)/n, size=1)[0]

        for idx, rel in enumerate(rel_associate_classifications):
            sys.stdout.write(rnd_array[idx] * ".")
            sys.stdout.flush()

            classification_reference = rel.RelatingClassification

            if ifc_file.schema == "IFC2X3":
                classification_reference_code = classification_reference.ItemReference
            else:
                classification_reference_code = classification_reference.Identification

            classification_reference_name = classification_reference.Name # Same
            classification = classification_reference.ReferencedSource #Same
            classification_name = classification.Name
        
            # String matching between bsdd and IFC name
            domain_name = get_domain_fuzzy(get_domains(), classification_name)
            
            if isinstance(domain_name, str):
                log_to_construct[classification_name] = domain_name
            else:   
                if domain_name['name'] not in log_to_construct.keys():
                    log_to_construct[domain_name['name']] = {}
        
                log_to_construct[domain_name['name']][classification_reference_name +"-"+classification_reference_code] = {}

                json_shortcut = log_to_construct[domain_name['name']][classification_reference_name +"-"+classification_reference_code]

                bsdd_response = get_classification(domain_name['name'], str(classification_reference_code))

                if not isinstance(bsdd_response, str):
                    bsdd_response = get_classification_object(bsdd_response['namespaceUri'])
                    
                    if 'classificationProperties' in bsdd_response.keys():
                        json_shortcut['requirements'] = {}
                        json_shortcut['types'] = []
                        json_shortcut['values'] = {}

                        json_shortcut['requirements'] = bsdd_response['classificationProperties']
                        json_shortcut['types'] = bsdd_response['relatedIfcEntityNames']
                        
                    
                        for e in rel.RelatedObjects:

                            for p in json_shortcut['requirements']:
                                if not e.GlobalId in  json_shortcut['values'].keys():
                                    json_shortcut['values'][e.GlobalId] = []

                                checking = {"pset":0, "pname":0, "ptype":0}

                                name = p['name']
                                pset_spec = p['propertySet']
                                ptype = p['dataType']
                        
                                if pset_spec:
                                    props = ifcopenshell.util.element.get_psets(e)
                                    pset = props.get(pset_spec)

                                    if pset:
                                        checking["pset"] = 1
                                        val = pset.get(name) 
                                        if val is not None:
                                            checking["pname"] = 1  
                                        else:
                                            val = "No property found in the instance property set"     
                                else:
                                    pset_spec = "No property set specified in the bSDD."
                                    name = "NaN"

                                
                                di = {
                                    "name": name,
                                    "propertyset": pset_spec,
                                    "value": val,
                                    "type":ptype,
                                    "result":1
                                }

                                
                                json_shortcut['values'][e.GlobalId].append(di)
            
    else:
        log_to_construct['result'] = "No classification detected in the file."


    detailed_results_path = os.path.join(os.getcwd(), "dresult_bsdd.json")

    with open(detailed_results_path, 'w', encoding='utf-8') as f:
        json.dump(log_to_construct, f, ensure_ascii=False, indent=4)
        

if __name__ == "__main__":
    start_time = time.time()

    # mvd_fn= os.path.join(os.path.dirname(__file__), "ifcopenshell/mvd/mvd_examples/xset.mvdxml")
    # rule_tree = get_xset_rule(mvd_fn, "pset")

    simple_type_python_mapping = {
        # @todo should include unicode for Python2
        "string": str,
        "integer": int,
        "real": float,
        "number": float,
        "boolean": bool,
        "logical": bool,  # still not implemented in IfcOpenShell
        "binary": str,  # maps to a str of "0" and "1"
    }

    ifc_fn = sys.argv[1]
    ifc_file = ifcopenshell.open(ifc_fn)

    validate_consistency(ifc_file)
    # print("--- %s seconds ---" % (time.time() - start_time))

    results_path = os.path.join(os.getcwd(), "result_bsdd.json")

    # if passed == 1:
    #     bsdd_result = {'mvd':'v'}
    # elif passed == 0:
    #     bsdd_result = {'mvd':'i'}

    bsdd_result = {'mvd':'i'}

    try:
        config_path = os.path.join(os.getcwd(), "config.json")
        with open(config_path) as json_file:
            config = json.load(json_file)

            config["results"]["bsddlog"] = "v"
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    
    except:
        pass

    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(bsdd_result, f, ensure_ascii=False, indent=4)
    









