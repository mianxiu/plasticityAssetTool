

from enum import Enum
from functools import wraps



# def convert_to_js_dispatchEvent_str(enum_class):
#     original_str_method = enum_class.__str__

#     @wraps(original_str_method)
#     def modified_str_method(self) -> str:
#         _self_class_name = self.__class__.__name__
#         if _self_class_name == "PointerEvent":
#             _event_str = f"""var e = new PointerEvent("{self.value}");targetElement.dispatchEvent(e);"""
#         else:
#             _event_command_str = f'''{_self_class_name}:{self.value}'''.lower() 
#             _event_str = f"""var e = new Event("{_event_command_str}");targetElement.dispatchEvent(e);"""
#         return _event_str
    
#     enum_class.__str__ = modified_str_method
#     return enum_class


def _convert_javascript_event_str(event_type):
    def cdp_decorator(func):
        @wraps(func)
        def cdp_payload_str(self,*args, **kwargs):
            
            if event_type == Javscript_Event_Type.EVENT.value:
                _event_command_str = f'''{self.__class__.__name__}:{self.value}'''.lower()
            else:              
                _event_command_str = f'''{self.value}'''.lower()
            _event_str = f"""document.querySelector('{kwargs["selector"]}').dispatchEvent(new {event_type}('{_event_command_str}'));"""
            #_event_str = f"""var targetElement = document.querySelector('{kwargs["selector"]}');var e = new {event_type}('{_event_command_str}');targetElement.dispatchEvent(e);"""
            #print(_event_str)
            
            result = func(self,*args,**kwargs)
            return _event_str
        return cdp_payload_str
    return cdp_decorator
            

class Javscript_Event_Type(Enum):
    EVENT= "Event"
    POINTER_EVENT = "PointerEvent"



class App(Enum):
    
    __JS_EVENT_TYPE = Javscript_Event_Type.EVENT.value

    NEW_WINDOW = 'new-window'
    QUIT ='quit'



class Command(Enum):
    
    _JS_EVENT_TYPE = Javscript_Event_Type.EVENT.value
    
    @_convert_javascript_event_str(event_type=_JS_EVENT_TYPE)
    def _selector(self,selector:str):
        pass
    
    # def _selector(self,selector:str):
    #     _event_command_str = f'''{self.__class__.__name__}:{self.name}'''.lower() 
    #     _event_str = f"""var targetElement = document.querySelector('{selector}');var e = new Event('{_event_command_str}');targetElement.dispatchEvent(e);"""
    #     return _event_str
    

    
    
    ABORT="abort"
    ALTERNATIVE_DUPLICATE="alternative-duplicate"
    BOOLEAN="boolean"
    BRIDGE="bridge"
    BRIDGE_CURVE="bridge-curve"
    BRIDGE_EDGE="bridge-edge"
    BRIDGE_SURFACE="bridge-surface"
    BRIDGE_VERTEX="bridge-vertex"
    CENTER_BOX="center-box"
    CENTER_CIRCLE="center-circle"
    CENTER_POINT_ARC="center-point-arc"
    CENTER_RECTANGLE="center-rectangle"
    CHECK="check"
    CONSTRAINED_SURFACE="constrained-surface"
    CONTROL_POINT_CURVE="control-point-curve"
    CONVERT_VERTEX="convert-vertex"
    COPY_WITH_PLACEMENT="copy-with-placement"
    CORNER_BOX="corner-box"
    CORNER_RECTANGLE="corner-rectangle"
    CREATE_OUTLINE="create-outline"
    CREATE_SOLID_FROM_FACES="create-solid-from-faces"
    CREATE_VIEWSPACE_CONSTRUCTION_PLANE="create-viewspace-construction-plane"
    CREATE_VIEWSPACE_CONSTRUCTION_PLANE_AT_ORIGIR="create-viewspace-construction-plane-at-origir"
    CURVE="curve"
    CURVE_ARRAY="curve-array"
    CUT="cut"
    CUT_CURVE="cut-curve"
    CYLINDER="cylinder"
    DELETE="delete"
    DELETE_CONTROL_POINT="delete-control-point"
    DELETE_EDGE="delete-edge"
    DELETE_FACE="delete-face"
    DELETE_GROUP="delete-group"
    DELETE_REDUNDANT_TOPOLOGY="delete-redundant-topology"
    DESELECT_ALL="deselect-all"
    DIALOG_PLACE="dialog:place"
    DIMENSION="dimension"
    DISSOLVE="dissolve"
    DISSOLVE_FACE="dissolve-face"
    DRAFT_FACE="draft-face"
    DUPLICATE="duplicate"
    DUPLICATE_CURVE_AND_PROJECT="duplicate-curve-and-project"
    DUPLICATE_EDGE_AND_PROJECT="duplicate-edge-and-project"
    EXPORT_CAD="export-cad"
    EXPORT_OBJ="export-obj"
    EXPORT_STL="export-stl"
    EXTEND="extend"
    EXTEND_CURVE="extend-curve"
    EXTEND_EDGE="extend-edge"
    EXTEND_SHEET="extend-sheet"
    EXTRUDE="extrude"
    FILLET="fillet"
    FILLET_CURVE="fillet-curve"
    FILLET_SHELL="fillet-shell"
    FILLET_VERTEX="fillet-vertex"
    FIND_BOUNDARY_EDGES="find-boundary-edges"
    FINISH="finish"
    FREESTYLE_MIRROR="freestyle-mirror"
    FREESTYLE_MOVE="freestyle-move"
    FREESTYLE_MOVE_ITEM="freestyle-move-item"
    FREESTYLE_OFFSET_PLANAR_CURVE="freestyle-offset-planar-curve"
    FREESTYLE_ROTATE="freestyle-rotate"
    FREESTYLE_ROTATE_ITEM="freestyle-rotate-item"
    FREESTYLE_SCALE="freestyle-scale"
    FREESTYLE_SCALE_ITEM="freestyle-scale-item"
    GROUP_SELECTED="group-selected"
    HIDE_SELECTED="hide-selected"
    HIDE_UNSELECTED="hide-unselected"
    HOLLOW="hollow"
    HOLLOW_SOLID="hollow-solid"
    IMPRINT="imprint"
    IMPRINT_BODY_BODY="imprint-body-body"
    IMPRINT_CURVE_BODY="imprint-curve-body"
    INSERT_KNOT="insert-knot"
    INVERT_HIDDEN="invert-hidden"
    INVERT_SELECTION="invert-selection"
    ISOLATE="isolate"
    ISOPARAM="isoparam"
    JOIN="join"
    JOIN_CURVES="join-curves"
    JOIN_SHEETS="join-sheets"
    LINE="line"
    LOCK_SELECTED="lock-selected"
    LOFT="loft"
    LOFT_GUIDE="loft-guide"
    MATCH_FACE="match-face"
    MEASURE="measure"
    MIRROR="mirror"
    MOVE="move"
    MOVE_CONTROL_POINT="move-control-point"
    MOVE_EMPTY="move-empty"
    MOVE_FACE="move-face"
    MOVE_ITEM="move-item"
    OFFSET_CURVE="offset-curve"
    OFFSET_EDGE="offset-edge"
    OFFSET_FACE="offset-face"
    OFFSET_FACE_LOOP="offset-face-loop"
    OFFSET_PLANAR_CURVE="offset-planar-curve"
    OFFSET_REGION="offset-region"
    OFFSET_VERTEX="offset-vertex"
    PASTE_WITH_PLACEMENT="paste-with-placement"
    PATCH="patch"
    PIPE="pipe"
    PLACE="place"
    POLYGON="polygon"
    PROJECT="project"
    PROJECT_BODY_BODY="project-body-body"
    PROJECT_CURVE_BODY="project-curve-body"
    PROJECTCURVE_CURVE="projectcurve-curve"
    PROJECT_OUTLINE="project-outline"
    PUSH_FACE="push-face"
    QUASIMODE_START="quasimode:start"
    QUASIMODE_STOP="quasimode:stop"
    RADIAL_ARRAY="radial-array"
    REBUILD="rebuild"
    REBUILD_CURVE="rebuild-curve"
    REBUILD_FACE="rebuild-face"
    RECTANGULAR_ARRAY="rectangular-array"
    REFILLET_FACE="refillet-face"
    REMOVE_FILLETS_FROM_SHELL="remove-fillets-from-shell"
    REMOVE_ITEM="remove-item"
    REMOVE_MATERIAL="remove-material"
    REVOLVE="revolve"
    ROTATE="rotate"
    ROTATE_CONTROL_POINT="rotate-control-point"
    ROTATE_EMPTY="rotate-empty"
    ROTATE_FACE="rotate-face"
    ROTATE_ITEM="rotate-item"
    SCALE="scale"
    SCALE_CONTROL_POINT="scale-control-point"
    SCALE_EMPTY="scale-empty"
    SCALE_FACE="scale-face"
    SCALE_ITEM="scale-item"
    SELECT_ADJACENT="select-adjacent"
    SELECT_A11="select-a11"
    SELECT_ALL_CURVES="select-all-curves"
    SELECT_NEXT_ENTITY_COLLECTION="select-next-entity-collection"
    SELECT_PREVIOUS_ENTITY_COLLECTION="select-previous-entity-collection"
    SET_MATERIAL="set-material"
    SMART_COMMAND="smart-command"
    SPHERE="sphere"
    SPIRAL="spiral"
    SPLIT_SEGMENT="split-segment"
    SUBDIVIDE_CURVE="subdivide-curve"
    SWEEP="sweep"
    SWEEP_TOOL="sweep-tool"
    TANGENT_ARC="tangent-arc"
    TANGENT_CIRCLE="tangent-circle"
    TEXT="text"
    THICKEN="thicken"
    THICKEN_FACE="thicken-face"
    THICKEN_SHEET="thicken-sheet"
    THREE_POINT_ARC="three-point-arc"
    THREE_POINT_BOX="three-point-box"
    THREE_POINT_CIRCLE="three-point-circle"
    THREE_POINT_RECTANGL="three-point-rectangl"
    TRIM="trim"
    TWO_POINT_CIRCLE="two-point-circle"
    UNDO="undo"
    UNGROUP_SELECTED="ungroup-selected"
    UNHIDE_ALL="unhide-all"
    UN_JOIN="unjoin"
    UNJOIN_CURVES="unjoin-curves"
    UNJOIN_FACES="unjoin-faces"
    UNJOIN_SHELLS="unjoin-shells"
    UNTRIM="untrim"
    UNWRAP_FACE="unwrap-face"
    WRAP_FACE="wrap-face"
    # 
    Set_NAME="set-name"


class PointerEvent(Enum):
  
        _JS_EVENT_TYPE = Javscript_Event_Type.POINTER_EVENT.value
        
        @_convert_javascript_event_str(event_type=_JS_EVENT_TYPE)
        def _selector(self,selector:str):
            pass
    
        
        POINTER_UP="pointerup"
        POINTER_MOVE="pointermove"
        POINTER_DOWN="pointerdown"
        POINTER_ENTER="pointerenter"
        
        
class Edit(Enum):
    
    _JS_EVENT_TYPE = Javscript_Event_Type.EVENT.value
        
    @_convert_javascript_event_str(event_type=_JS_EVENT_TYPE)
    def _selector(self,selector:str):
            pass
    
    COPY="copy"
    COP_WITH_PLACEMENT="copy-with-placement"
    PASTE="paste"
    PAST_WITH_PLACEMENT="paste-with-placement"
    REDO="redo"
    REPEA_LAS_COMMAND="repeat-last-command"
    UNDO="undo"
    
    
class Viewport(Enum):
    _JS_EVENT_TYPE = Javscript_Event_Type.EVENT.value
    
    @_convert_javascript_event_str(event_type=_JS_EVENT_TYPE)
    def _selector(self,selector:str):
            pass
        
    CPLANE_RESET="cplane:reset"
    CPLANE_SELECTION="cplane:selection"
    FOCUS="focus"
    GRID_DECR="grid:decr"
    GRID_INCR="grid:incr"
    NAVIGATE_BACK="navigate:back"
    NAVIGATE_BOTTOM="navigate:bottom"
    NAVIGATE_FRONT="navigate:front"
    NAVIGATE_LEFT="navigate:left"
    NAVIGATE_RIGHT="navigate:right"
    NAVIGATE_SELECTION="navigate:selection"
    NAVIGATE_TOP="navigate:top"
    SET_AND_CENTER_FOCUS_POINT="set-and-center-focus-point"
    SET_FOCUS_POINT="set-focus-point"
    TOGGLE_EDGES="toggle-edges"
    TOGGLE_FACES="toggle-faces"
    TOGGLE_ORTHOGRAPHIC="toggle-orthographic"
    TOGGLE_OVERLAYS="toggle-overlays"
    TOGGLE_RENDER_MODE="toggle-render-mode"
    TOGGLE_X_RAY="toggle-x-ray"
        
        
    