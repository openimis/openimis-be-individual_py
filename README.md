# openIMIS Backend individual reference module
This repository holds the files of the openIMIS Backend Individual reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

## ORM mapping:
* individual_individual, individual_historicalindividual > Individual
* individual_individuallabel, individual_historicalindividuallabel > IndividualLabel
* individual_individualdatasource, individual_historicalindividualdatasource > IndividualDataSource
* individual_individualdatasourceupload, individual_historicalindividualdatasourceupload > IndividualDataSourceUpload
* individual_group, individual_historicalgroup > Group
* individual_groupindividual, individual_historicalgroupindividual > GroupIndividual

## GraphQl Queries
* individual (`labels: [String]` returns individuals carrying any of the given label codes)
* individualLabel
* individualDataSource
* individualDataSourceUpload
* group
* groupIndividual
* groupExport
* individualExport
* groupIndividualExport

## GraphQL Mutations - each mutation emits default signals and return standard error lists (cfr. openimis-be-core_py)
* createIndividual
* updateIndividual
* deleteIndividual
* createIndividualLabel
* updateIndividualLabel
* deleteIndividualLabel
* assignIndividualLabels
* updateIndividualSchema
* createGroup
* updateGroup
* deleteGroup
* addIndividualToGroup
* editIndividualInGroup
* removeIndividualFromGroup
* createGroupIndividuals

## Services
- Individual
  - create
  - update
  - delete
  - update_labels
- IndividualLabel
  - create
  - update
  - delete
- IndividualDataSource
  - create
  - update
  - delete
- Group
  - create
  - update
  - delete
  - create_group_individuals
  - update_group_individuals
- GroupIndividualService
  - create
  - update
  - delete

## Configuration options (can be changed via core.ModuleConfiguration)
* gql_individual_search_perms: required rights to call individual GraphQL Query (default: ["159001"])
* gql_individual_create_perms: required rights to call createIndividual GraphQL Mutation (default: ["159002"])
* gql_individual_update_perms: required rights to call updateIndividual GraphQL Mutation (default: ["159003"])
* gql_individual_delete_perms: required rights to call deleteIndividual GraphQL Mutation (default: ["159004"])
* gql_group_search_perms: required rights to call group GraphQL Mutation (default: ["180001"])
* gql_group_create_perms: required rights to call createGroup and addIndividualToGroup and createGroupIndividuals GraphQL Mutation (default: ["180002"])
* gql_group_update_perms: required rights to call updateGroup and editIndividualInGroup GraphQL Mutation (default: ["180003"])
* gql_group_delete_perms: required rights to call deleteGroup and removeIndividualFromGroup GraphQL Mutation (default: ["180004"])

## Label and schema rights
Declared in the module's rights table (`individual/apps.py`) and not configurable through `core.ModuleConfiguration`:
* 159006 (`individual.add_individuallabel`): createIndividualLabel
* 159007 (`individual.change_individuallabel`): updateIndividualLabel
* 159008 (`individual.delete_individuallabel`): deleteIndividualLabel
* 159009 (`individual.change_individual_schema`): updateIndividualSchema

Reading labels needs the individual search right (159001); `assignIndividualLabels` needs the individual update right (159003).


## openIMIS Modules Dependencies
- core


## Enabling Python Workflows
Module comes with simple workflows for individual data upload. 
They should be used for the development purposes, not in production environment. 
To activate these Python workflows, a configuration change is required. 
Specifically, the `enable_python_workflows` parameter to `true` within module config.

Workflows: 
 * individual upload


## Labels

An individual carries zero or more label codes saying what kind of person it is (for example `INSUREE`,
`PRACTITIONER`, `CLAIM_ADMIN`, `BENEFICIARY`, which are created by the migrations when a user exists).

* Labels are defined in `IndividualLabel`: a `code` (uppercase letters, digits and `_`, unique), a `name`
  and an optional JSON schema that individuals with this label are expected to follow. Its properties must be
  fields of the individual schema (see *Additional Field Definition*), with the same type, and it follows the
  same field rules.
  The schema is informational: it is returned by GraphQL and used by the advanced filters when the
  `label` additional parameter is passed, but `json_ext` is not validated against it.
* The codes are stored on the individual itself (`Individual.labels`, a PostgreSQL array with a GIN index),
  so filtering by label needs no join. For the same reason a code cannot be changed, and a label cannot be
  deleted while any individual, including a deleted one, still carries it.
* Labels are set on `createIndividual` / `updateIndividual` (the list replaces the current one, `[]` clears it),
  in bulk with `assignIndividualLabels(ids, add, remove)`, which does not go through maker-checker,
  and from a `labels` column in upload files (codes separated by `;`). In update files an empty cell clears
  the labels and a missing column leaves them unchanged. Unknown codes are rejected when the request or the
  upload is validated; a label deleted between an upload's validation and its approval is dropped from the rows.
* A label cannot be deleted while an individual carries it or a pending update task would add it.
  `NA` and `NULL` are reserved: spreadsheet readers treat those cells as empty.

## Additional Field Definition

Individual model comes with a minimal set of fields: `first_name`, `last_name`, `dob`.
The additional fields are described by the `individual_schema` of the module configuration. It is the one
catalogue of those fields: label schemas, and the beneficiary data schemas of the social protection module, are
built from its fields and must use each with the same type.

The `updateIndividualSchema(schema)` mutation (right 159009) validates and saves it. The same field rules apply to
label and benefit plan schemas:

* each property needs a `type` among `string`, `integer`, `decimal`, `date` and `boolean` (the types the
  advanced filters handle); `decimal` and `date` are accepted although they are not JSON Schema types, the rest
  of the schema is checked as JSON Schema draft 7;
* property names must not be empty, contain `__` or `=`, or end with `_` (they become filter lookups);
* optional `description` (text), `uniqueness` (only `true`: the upload validation treats the key's presence as
  unique, so omit it instead of writing `false`) and `validationCalculation` (`{"name": ...}`);
* a field used by a label or a benefit plan, deleted ones included, cannot be removed or change type.

A module whose model stores a schema built from these fields registers it with
`individual.schema_usage.register_schema_owner(model, code_field, schema_field)` from its `ready()`; labels and
benefit plans are registered this way. `python manage.py check_individual_schema_usage` lists the stored schemas
that use fields the individual schema lacks, or with another type (for instance benefit plans created before this
rule, which keep working until their schema is edited), and exits with an error when it finds any.

The saved schema takes effect in every server process without a restart: readers compare the stored
configuration with what their process last loaded and reload it when another process changed it.

The configuration can also be edited in the backend admin interface, which does not apply these rules, by adding
a Module configuration for `individual`:

1. In the web app, visit URL path `/api/admin/core/moduleconfiguration` in browser
2. Click on ADD MODULE CONFIGURATION
3. Fill in the form with the following values:
    - Module: individual
    - Layer: backend
    - Version: 1
    - Config: `{"individual_schema": "{\"$id\": \"https://example.com/beneficiares.schema.json\", \"type\": \"object\", \"title\": \"Record of beneficiares\", \"$schema\": \"http://json-schema.org/draft-04/schema#\", \"properties\": {\"email\": {\"type\": \"string\", \"description\": \"email address to contact with beneficiary\", \"validationCalculation\": {\"name\": \"EmailValidationStrategy\"}}, \"able_bodied\": {\"type\": \"boolean\", \"description\": \"Flag determining whether someone is able bodied or not\"}, \"national_id\": {\"type\": \"string\", \"description\": \"national id\"}, \"educated_level\": {\"type\": \"string\", \"description\": \"The level of person when it comes to the school/education/studies\"}, \"chronic_illness\": {\"type\": \"boolean\", \"description\": \"Flag determining whether someone has such kind of illness or not\"}, \"national_id_type\": {\"type\": \"string\", \"description\": \"A type of national id\"}, \"number_of_elderly\": {\"type\": \"integer\", \"description\": \"Number of elderly\"}, \"number_of_children\": {\"type\": \"integer\", \"description\": \"Number of children\"}, \"beneficiary_data_source\": {\"type\": \"string\", \"description\": \"The source from where such beneficiary comes\"}}, \"description\": \"This document records the details beneficiares\"}"}`
   Modify the `Config` value accordingly with your individual additional field definitions.
4. Click on SAVE

### Generate dummy individuals for development

**Requirements**

- [openimis-be_py](https://github.com/openimis/openimis-be_py) repo is cloned and setup locally. Django command execution requires this repo.
- Ensure all dependencies are installed, see openimis-be_py [README](https://github.com/openimis/openimis-be_py/blob/develop/README.md#developers-setup)

First, generate a csv file with a list of individuals which can be used for uploading:

```bash
# go to the openimis-be_py repo, openIMIS folder
cd ../openimis-be_py/openIMIS/

python manage.py fake_individuals
```

The `fake_individuals` command generates 100 individuals using the sample `individual_schema` provided above.
Feel free to modify the fields and number of individuals as needed.
The last line of the output should provide the path to the temporary csv file that contains the list of dummy individuals.

Then upload the generated csv file in the web app:
- Go to "Social Protection" > "Individuals" > "UPLOAD" and select the generated csv as the file to upload.
- Choose "Python Import Individuals" as the Workflow, leave "Create groups from column:" empty, then click on UPLOAD INDIVIDUALS.
- Go to "Task Management" > "All Tasks", find and approve the `import_valid_items` task.
- Then you should see the list of individuals appear under "Social Protection" > "Individuals"
