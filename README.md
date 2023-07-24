# openIMIS Backend individual reference module
This repository holds the files of the openIMIS Backend Individual reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

## ORM mapping:
* individual_individual, individual_historicalindividual > Individual
* individual_individualdatasource, individual_historicalindividualdatasource > IndividualDataSource
* individual_individualdatasourceupload, individual_historicalindividualdatasourceupload > IndividualDataSourceUpload
* individual_group, individual_historicalgroup > Group
* individual_groupindividual, individual_historicalgroupindividual > GroupIndividual

## GraphQl Queries
* individual
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


## openIMIS Modules Dependencies
- core
