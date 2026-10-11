"""The bid negotiation rules: who may do what, and what happens next. Illegal moves are refused (HTTP 409)."""
from app.core.exceptions import ConflictError


class IllegalBidAction(ConflictError):
    """That move is not allowed now (wrong turn, finished bid, unknown action)."""


class BidRules:
    # state -> actions allowed; the side that acts must be the side whose turn it is
    ALLOWED = {"invited": {"accept", "counter", "decline"}, "countered": {"accept", "counter", "decline"},
               "accepted": set(), "declined": set()}
    OTHER = {"gov": "vendor", "vendor": "gov"}

    def next(self, status: str, turn: str, side: str, action: str) -> tuple[str, str]:
        """(new status, new turn) for `side` doing `action` on a bid in `status` whose turn is `turn`."""
        if action not in self.ALLOWED.get(status, set()):
            raise IllegalBidAction(f"cannot {action} a bid that is {status}")
        if side != turn:
            raise IllegalBidAction(f"it is the {turn} side's turn")
        if action == "counter":
            return "countered", self.OTHER[side]
        return ("accepted" if action == "accept" else "declined"), "none"
