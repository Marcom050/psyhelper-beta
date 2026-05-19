from services import auth_service


def main():
    issues=[]
    repo=auth_service.get_account_repository()
    usernames = repo.list_usernames() if hasattr(repo, 'list_usernames') else []
    for username in usernames:
        md=auth_service.load_user_metadata(username)
        if not md.get('tenant_id'): issues.append((username,'missing_tenant_id'))
        if md.get('role') not in {'client','therapist'}: issues.append((username,'invalid_role'))
    if issues:
        for u,i in issues: print(f'{u}: {i}')
        raise SystemExit(1)
    print('auth readiness ok')

if __name__=='__main__':
    main()
