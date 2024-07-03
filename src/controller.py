from typing import Dict
from os.path import basename
from fabric import Connection
from .io import IO
from .view import View


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


class ActionLoadParameters(Action):

    def exec(self):
        file = self.view.file_dialog_open()
        if file == '':
            return

        try:
            parameters = self.io.read(file=file)
            self.view.set_parameters(parameters=parameters)
        except Exception as e:
            self.view.message_box_error(msg=str(e))


class ActionSaveParameters(Action):

    def exec(self):
        file = self.view.file_dialog_save()
        if file == '':
            return

        try:
            parameters = self.view.get_key_values()
            self.io.write(file=file, parameters=parameters)
        except Exception as e:
            self.view.message_box_error(msg=str(e))


class ActionSubmit(Action):

    ROOT_DIR = '~/RNAapp'
    BASH_PROFILE = '.bash_profile'

    view: View

    ssh_password: str
    ssh_key_values: Dict[str, str]
    rna_key_values: Dict[str, str]
    con: Connection
    rna_cmd: str
    submit_cmd: str

    def exec(self):

        self.ssh_password = self.view.password_dialog()
        if self.ssh_password == '':
            return

        if not self.view.message_box_yes_no(msg='Are you sure you want to submit the job?'):
            return

        try:
            self.get_key_values()
            self.set_rna_cmd()
            self.set_submit_cmd()
            self.connect()
            self.submit_job()
            self.view.message_box_info(msg='Job submitted!')

        except Exception as e:
            self.view.message_box_error(msg=str(e))

    def get_key_values(self):
        self.ssh_key_values = self.view.get_ssh_key_values()
        self.rna_key_values = self.view.get_rna_key_values()

    def set_rna_cmd(self):
        program = self.ssh_key_values['RNA-Seq Analysis']
        outdir = self.rna_key_values['outdir']

        args = [f'python {program}']
        for key, val in self.rna_key_values.items():
            if type(val) is bool:
                if val is True:
                    args.append(f'--{key}')

            else:  # val is string
                args.append(f"--{key}='{val}'")

        args.append(f'2>&1 | tee {outdir}/progress.txt')  # `2>&1` stderr to stdout --> tee to progress.txt

        self.rna_cmd = ' '.join(args)

        if '"' in self.rna_cmd:
            print('Warning: double quotes in the RNA-Seq Analysis command will be replaced by single quotes', flush=True)
            # self.rna_cmd will be wrapped in double quotes in self.submit_cmd
            # so double quotes needs to be avoided
            self.rna_cmd = self.rna_cmd.replace('"', '\'')

    def set_submit_cmd(self):
        outdir = self.rna_key_values['outdir']
        job_name = basename(outdir).replace(' ', '_')
        sample_sheet = self.rna_key_values['sample-info-table']

        # the environment (.bash_profile) needs to be activated right before the rna_cmd
        script = f'source {self.BASH_PROFILE} && {self.rna_cmd}'
        cmd_txt = f'{outdir}/command.txt'

        self.submit_cmd = ' && '.join([
            f'mkdir -p "{outdir}"',
            f'cp "{sample_sheet}" "{outdir}/"',
            f'echo "{script}" > "{cmd_txt}"',
            f'screen -dm -S {job_name} bash "{cmd_txt}"'
        ])

    def connect(self):
        s = self.ssh_key_values
        self.con = Connection(
            host=s['Host'],
            user=s['User'],
            port=int(s['Port']),
            connect_kwargs={'password': self.ssh_password}
        )

    def submit_job(self):
        with self.con.cd(self.ROOT_DIR):
            self.con.run(self.submit_cmd, echo=True)  # echo=True for printing out the command
        self.con.close()
