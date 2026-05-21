from fabric import Connection
from typing import Dict, Optional
from os.path import basename, abspath
from .io import IO
from .view import View


REMOTE_ROOT_DIR = 'RNAapp'  # placed in the remote user's home directory
PROFILE_FILE = '.profile'


class Controller:

    view: View

    def __init__(self, io: IO, view: View):
        self.io = io
        self.view = view
        self.__connect_buttons_to_actions()
        self.view.show()

    def __connect_buttons_to_actions(self):
        for button in self.view.button_dict.values():
            key = button.key
            qbutton = button.qbutton
            action_method = getattr(self, f'action_{key}', None)
            if action_method is not None:
                qbutton.clicked.connect(action_method)
            else:
                print(f'Warning: method "action_{key}" not found in the Controller class', flush=True)

    def action_basic_mode(self):
        self.view.show_basic_mode()

    def action_advanced_mode(self):
        self.view.show_advanced_mode()

    def action_load_parameters(self):
        ActionLoadParameters(self).exec()

    def action_save_parameters(self):
        ActionSaveParameters(self).exec()

    def action_submit(self):
        ActionSubmit(self).exec()


class Action:

    io: IO
    view: View

    def __init__(self, controller: Controller):
        self.io = controller.io
        self.view = controller.view

    def exec(self):
        try:
            self.workflow()
        except Exception as e:
            self.view.message_box_error(msg=repr(e))


class ActionLoadParameters(Action):

    def workflow(self):
        file = self.view.file_dialog_open(title='Load Parameters')
        if file == '':
            return
        parameters = self.io.read(file=file)
        self.view.set_parameters(parameters=parameters)


class ActionSaveParameters(Action):

    def workflow(self):
        file = self.view.file_dialog_save()
        if file == '':
            return
        parameters = self.view.get_key_values()
        self.io.write(file=file, parameters=parameters)


class ActionSubmit(Action):

    count_table_local_path: str
    sample_info_table_local_path: str
    gene_info_table_local_path: str
    gene_sets_gmt_local_path: str

    ssh_password: str
    ssh_key_values: Dict[str, str]
    rna_key_values: Dict[str, str]
    rna_cmd: str

    def workflow(self):
        self.count_table_local_path = self.view.file_dialog_open(title='Upload Count Table')
        if self.count_table_local_path == '':
            return
        self.sample_info_table_local_path = self.view.file_dialog_open(title='Upload Sample Info Table')
        if self.sample_info_table_local_path == '':
            return
        self.gene_info_table_local_path = self.view.file_dialog_open(title='Upload Gene Info Table')
        if self.gene_info_table_local_path == '':
            return
        self.gene_sets_gmt_local_path = self.view.file_dialog_open(title='Upload Gene Sets GMT File (optional)')

        self.ssh_password = self.view.password_dialog()
        if self.ssh_password == '':
            return

        if not self.view.message_box_yes_no(msg='Are you sure you want to submit the job?'):
            return

        self.ssh_key_values = self.view.get_ssh_key_values()
        self.rna_key_values = self.view.get_rna_key_values()

        self.build_rna_cmd()
        self.connect_and_submit_job()
        self.view.message_box_info(msg='Job submitted!')

    def build_rna_cmd(self):
        program = self.ssh_key_values['RNA-Seq Analysis']
        outdir = self.rna_key_values['outdir']

        args = [f'python {program}']
        for key, val in self.rna_key_values.items():
            if type(val) is bool:
                if val is True:
                    args.append(f'--{key}')
            else:  # val is string
                args.append(f"--{key}='{val}'")
        
        args.append(f"--count-table='{outdir}/{basename(self.count_table_local_path)}'")  # uploaded by the user
        args.append(f"--sample-info-table='{outdir}/{basename(self.sample_info_table_local_path)}'")
        args.append(f"--gene-info-table='{outdir}/{basename(self.gene_info_table_local_path)}'")
        if self.gene_sets_gmt_local_path != '':
            args.append(f"--gene-sets-gmt='{outdir}/{basename(self.gene_sets_gmt_local_path)}'")
        args.append(f"2>&1 | tee '{outdir}/progress.txt'")
        self.rna_cmd = '     '.join(args)

    def connect_and_submit_job(self):
        """
        Shell characters like './' and '~/' will work in con.run(), but not in con.put()
        
        To be safe, use absolute path for the remote root dir
        The outdir is defined as relative path, but check if it traverses outside the remote root dir (security issues)
        """
        s = self.ssh_key_values
        con = Connection(
            host=s['Host'],
            user=s['User'],
            port=int(s['Port']),
            connect_kwargs={'password': self.ssh_password}
        )

        user = self.ssh_key_values['User']
        remote_root = f'/home/{user}/{REMOTE_ROOT_DIR}'  # absolute path
        outdir = self.rna_key_values['outdir']  # relative path

        assert is_subdir(parent=remote_root, child=f'{remote_root}/{outdir}'), \
            f'The outdir "{outdir}" traverses outside the remote root directory, not safe!'

        with con.cd(remote_root):
            con.run(f'mkdir -p "{outdir}"', echo=True)

        for local_path in [
            self.count_table_local_path,
            self.sample_info_table_local_path,
            self.gene_info_table_local_path,
            self.gene_sets_gmt_local_path,
        ]:
            if local_path == '':
                continue
            print(f'Uploading "{basename(local_path)}" to remote directory "{remote_root}/{outdir}/"', flush=True)
            con.put(
                local=local_path,
                remote=f'{remote_root}/{outdir}/'  # absolute path
            )

        # the environment (.profile) needs to be activated right before the rna_cmd
        script = f'source {PROFILE_FILE} && {self.rna_cmd}'
        cmd_txt = f'{outdir}/command.txt'
        job_name = basename(outdir).replace(' ', '_')

        with con.cd(remote_root):
            con.run(f'echo "{script}" > "{cmd_txt}"', echo=True)
            con.run(f'screen -dm -S {job_name} bash "{cmd_txt}"', echo=True)

        con.close()


def is_subdir(parent: str, child: str) -> bool:
    p = abspath(parent)
    c = abspath(child)
    return c.startswith(p)
