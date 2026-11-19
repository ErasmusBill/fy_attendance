import random
import re
import string


def generate_temporal_password(length=8):
    letters = string.ascii_letters + string.digits
    password = ''.join(random.choice(letters) for _ in range(length))
    return password


def generate_member_id(prefix="FY", digits=4):
    """
    Generates a unique, formatted member ID in the format: FY-0011.

    Args:
        prefix (str): Prefix string (default: "FY").
        digits (int): Number of zero-padded numeric digits (default: 4).

    Returns:
        str: Formatted member ID (e.g., 'FY-0001', 'FY-0011').
    """
    next_number = 1

    try:
        from apps.members.models import Members

        # Check if Members model has a member_id field
        has_member_id = any(
            f.name == 'member_id' for f in Members._meta.get_fields()
        )

        if has_member_id:
            # Query all existing member_ids starting with the prefix
            existing_ids = Members.objects.filter(
                member_id__startswith=f"{prefix}-"
            ).values_list('member_id', flat=True)

            max_num = 0
            pattern = re.compile(rf'^{re.escape(prefix)}-(\d+)$')

            for mid in existing_ids:
                match = pattern.match(str(mid).strip())
                if match:
                    try:
                        num = int(match.group(1))
                        if num > max_num:
                            max_num = num
                    except ValueError:
                        continue

            next_number = max_num + 1

            # Ensure the generated ID does not collide with any existing record
            new_id = f"{prefix}-{next_number:0{digits}d}"
            while Members.objects.filter(member_id=new_id).exists():
                next_number += 1
                new_id = f"{prefix}-{next_number:0{digits}d}"

            return new_id
        else:
            # If member_id field does not yet exist on Members model,
            # calculate sequential ID based on total member count + 1
            count = Members.objects.count()
            next_number = count + 1

    except Exception:
        # Fallback if database or app registry is not yet ready
        pass

    return f"{prefix}-{next_number:0{digits}d}"
