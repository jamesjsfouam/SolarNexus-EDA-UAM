"""DC mesh optimization endpoint using the existing SciPy MILP model."""
from fastapi import APIRouter, HTTPException
from ...mesh import Enlace, Nodo, RedMeshDC
from ..schemas import MeshSolveCreate, MeshSolveRead
router = APIRouter(prefix="/mesh", tags=["DC Mesh"])
@router.post("/solve", response_model=MeshSolveRead)
def solve_mesh(payload: MeshSolveCreate) -> MeshSolveRead:
    network = RedMeshDC(
        nodos=[Nodo(nombre=node.name, generacion=node.generation_kwh, carga=node.demand_kwh) for node in payload.nodes],
        enlaces=[Enlace(origen=link.origin, destino=link.destination, capacidad=link.capacity_kwh,
            costo_transferencia=link.transfer_cost_per_kwh, perdida=link.loss_fraction,
            costo_switch=link.switch_cost) for link in payload.links],
        costo_ciclado=payload.central_cycling_cost_per_kwh,
    )
    try:
        result = network.resolver()
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo resolver la red: {exc}") from exc
    return MeshSolveRead(
        flows=[{"origin": origin, "destination": destination, "energy_kwh": energy}
            for (origin, destination), energy in result.flujos.items()],
        switches_closed=[{"origin": origin, "destination": destination}
            for origin, destination in result.switches_cerrados],
        central_supply_kwh=result.desde_central,
        curtailment_kwh=result.vertido,
        shadow_prices=result.precios_sombra,
        total_cost=result.costo_total,
    )
