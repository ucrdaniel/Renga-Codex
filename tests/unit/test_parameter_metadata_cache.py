"""Session metadata caching never substitutes for live saved-state reads."""
from types import SimpleNamespace

from renga_codex_bridge.model import parameters


GUID="{00000000-0000-4000-8000-0000000000AA}"


class Definition:
    def __init__(self,name="Mode",texts=("A","B")):
        self.Text="Description";self.Name=name;self.ParameterType=7
        self.ReferencedEntityTypeS="{00000000-0000-0000-0000-000000000000}"
        self.EnumerationItemTexts=texts


class Parameter:
    HasValue=True
    IsReadOnly=False
    ValueType=2
    def __init__(self,value=1,definition=None):
        self.value=value;self.definition=definition or Definition();self.definition_reads=0;self.value_reads=0
    @property
    def Definition(self):
        self.definition_reads+=1
        return self.definition
    def GetIntValue(self):self.value_reads+=1;return self.value
    def GetDoubleValue(self):self.value_reads+=1;return self.value


def context(parameter,guid=GUID):
    identifiers=SimpleNamespace(Count=1,GetS=lambda index:guid)
    container=SimpleNamespace(GetIds=lambda:identifiers,GetS=lambda identifier:parameter)
    return SimpleNamespace(sdk=SimpleNamespace(parameters={"Mode":GUID})),SimpleNamespace(GetParameters=lambda:container)


def test_repeated_reads_cache_definition_but_reread_current_value_readonly_and_hasvalue():
    parameter=Parameter();s,entity=context(parameter)
    first=parameters(s,entity)["Mode"]
    assert first["value"]==1 and not first["readonly"] and first["has_value"]
    parameter.value=8;parameter.IsReadOnly=True
    second=parameters(s,entity)["Mode"]
    assert second["value"]==8 and second["readonly"] and second["has_value"]
    parameter.HasValue=False
    third=parameters(s,entity)["Mode"]
    assert third["value"] is None and not third["has_value"] and third["readonly"]
    parameter.HasValue=True;parameter.ValueType=3;parameter.value=8.5
    fourth=parameters(s,entity)["Mode"]
    assert fourth["type"]==3 and fourth["value"]==8.5
    assert parameter.definition_reads==1 and parameter.value_reads==3


def test_new_session_rereads_definition_even_for_identical_guid_and_sdk_instance():
    parameter=Parameter(definition=Definition("First"));s,entity=context(parameter)
    assert parameters(s,entity)["Mode"]["definition_name"]=="First"
    parameter.definition=Definition("Second",("X","Y"))
    reopened=SimpleNamespace(sdk=s.sdk)
    assert parameters(reopened,entity)["Mode"]["definition_name"]=="Second"
    assert parameter.definition_reads==2


def test_same_guid_on_different_objects_reuses_only_definition_not_value_or_readonly():
    one=Parameter(3);two=Parameter(7);two.IsReadOnly=True
    s,entity_one=context(one);_,entity_two=context(two)
    assert parameters(s,entity_one)["Mode"]["value"]==3
    result=parameters(s,entity_two)["Mode"]
    assert result["value"]==7 and result["readonly"]
    assert one.definition_reads==1 and two.definition_reads==0 and two.value_reads==1


def test_caller_cannot_poison_cached_enumeration_list_or_metadata_dict():
    parameter=Parameter();s,entity=context(parameter)
    first=parameters(s,entity)["Mode"]
    first["enumeration_texts"].append("fake")
    first["text"]="fake"
    second=parameters(s,entity)["Mode"]
    assert second["enumeration_texts"]==["A","B"] and second["text"]=="Description"


def test_exact_result_shape_preserved_and_null_enumeration_is_an_empty_list():
    parameter=Parameter(definition=Definition(texts=None));s,entity=context(parameter)
    row=parameters(s,entity)["Mode"]
    assert list(row)==["guid","value","has_value","readonly","type","text","definition_name","parameter_type","referenced_entity_type","enumeration_texts"]
    assert row["enumeration_texts"]==[]
    assert row["guid"]==GUID and row["type"]==2


def test_case_variation_in_guid_does_not_retain_a_second_com_definition():
    parameter=Parameter();s,entity=context(parameter)
    parameters(s,entity)
    _,lower_entity=context(parameter,GUID.lower())
    assert parameters(s,lower_entity)["Mode"]["guid"]==GUID.lower()
    assert parameter.definition_reads==1
